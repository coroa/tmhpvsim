"""Hourly cloud cover model

For the hourly resolution, we use a Markov Chain; ie, if x[i] denotes the cloud
cover in time i then

.. code:: python

    x[i+1] = np.clip(x[i] + draw_random_step(x[i]), 0, 1)

where `draw_random_step` draws from one of 6 different distributions, depending
on the bin it falls into from (-1e-4, 0.1], (0.1, 0.3], (0.3, 0.7], (0.7, 0.9],
(0.9, 0.99], (0.99, 1.0].

We use MCMC based bayesian inference to estimate shape parameters for
modelling the distribution of step sizes in each bin from the hourly cloud
cover time-series of the ERA-5 reanalysis data set in the Munich grid cell.
Bin sizes as well as which distributions to use have been chosen by manual
investigation.

.. image:: img/distributions.png
"""

# %% importing modules
from pathlib import Path
import pvlib
import pymc3 as pm
import theano.tensor as tt
import pandas as pd
import xarray as xr
import numpy as np
%matplotlib inline
import matplotlib.pyplot as plt
import seaborn as sn
import cdsapi
import scipy.stats

import logging
logger = logging.getLogger(__name__)
logging.getLogger(pm.__name__).setLevel(logging.WARN)

# %% defining functions

def get_total_cloud_cover(lon, lat, path=None):
    """
    Download hourly cloud cover from ERA-5 of the Copernicus Climate Data Store

    Parameters
    ----------
    lon, lat : float
        Degrees of from where to use cloud cover data
    path : str|pathlib.Path, optional
        Path for caching the downloaded data. If None, use "tcc_<lon>_<lat>.nc"
        in working directory.

    Returns
    -------
    pd.Series
        Cloud cover time series
    """

    if path is None:
        path = Path(f"tcc_{lon}_{lat}.nc")
    else:
        path = Path(path)

    if not path.exists():
        logger.info("Downloading cloud cover for 2018")

        # ERA-5 uses a 0.25 degree global grid to get a single location we have to
        # buffer our wanted longitude and latitude by 0.25/2
        delta_2 = 0.25 / 2

        c = cdsapi.Client()

        c.retrieve(
            'reanalysis-era5-single-levels',
            {
                'product_type': 'reanalysis',
                'variable': 'total_cloud_cover',
                'year': list(range(2018, 2019)),
                'month': list(range(1,12+1)),
                'day': list(range(1, 31+1)),
                'time': [f'{i:02}:00' for i in range(0, 24)],
                'format':'netcdf',
                'area': [lat - delta_2,
                         lon - delta_2,
                         lat + delta_2,
                         lon + delta_2], # North, West, South, East
            },
            str(path)
        )

    return xr.open_dataset(path).isel(longitude=0, latitude=1).tcc.to_pandas()


# %% define new asymmetric_laplace distribution

class _asymmetric_laplace(scipy.stats.rv_continuous):
    """An asymmetric laplace distributed variable """

    def _pdf(self, x, kappa):
        return (1/(kappa + 1/kappa) *
                np.exp(np.where(x >= 0, -kappa, 1/kappa) * x))

    def _ppf(self, y, kappa):
        kappa_2 = kappa**2
        return np.where(y < kappa_2 / (1 + kappa_2),
                        kappa * np.log((1 + kappa_2) / kappa_2 * y),
                        -1/kappa * np.log((1 + kappa_2) * (1 - y)))

asymmetric_laplace = _asymmetric_laplace()

def asymmetric_laplace_tt_log_p(x, loc, scale, kappa):
    """Build theano tensor call graph for logarithmic pdf

    Notes
    -----
    Needed for modelling Asymmetric Laplace Distribution with PyMC's DensityDist
    """
    return (- tt.log(scale * (kappa + 1/kappa))
            - (x - loc) / scale * tt.switch(x - loc >= 0, kappa, -1/kappa))

def infer_distributions(tcc, create_plots=True, **sample_kwargs):
    """Infer distribution shape parameters from hourly cloud cover data

    Parameters
    ----------
    tcc : pd.Series
        Total cloud cover series from ERA-5
    create_plots : bool, optional
        Whether to create distribution plots, they are saved in the local
        working directory
    **sample_kwargs : dict, optional
        Extra parameters to `pm.sample`

    Returns
    -------
    shapes : pd.DataFrame
        Indexed with intervals and distribution parameters as columns

    See Also
    --------
    pm.sample

    Notes
    -----
    Based on total cloud cover variable of the ERA-5 dataset as distributed by
    the Copernicus Climate Change Service 2019, see also
    https://cds.climate.copernicus.eu/cdsapp#!/dataset/reanalysis-era5-single-levels
    """

    sample_kwargs.setdefault('draws', 8000)
    sample_kwargs.setdefault('tune', 8000)

    logger.info(f"Binning total_cloud_cover into: {list(groups)}")

    # For simplicity we use hand-chosen string markers from 'al' and 't' to
    # select which distribution to use for the data in each bin
    # 'al' marks Asymmetric Laplace distribution
    # 't' markes Student-T distribution
    dists = pd.Series(['al', 'al', 'al', 'al', 'al', 'al'], index=groups)

    shapes = []
    for group in groups:
        logger.info(f"##### Group {group} #######")

        with pm.Model() as model:
            loc = pm.Normal('loc', mu=0., sigma=1)
            scale = pm.HalfNormal('scale', sigma=1)

            if dists[group] == 'al':
                kappa = pm.HalfNormal('kappa', sigma=1)
                obs = pm.DensityDist(
                    'obs',
                    lambda x: asymmetric_laplace_tt_log_p(x, loc, scale, kappa),
                    observed=steps.loc[group]
                )
            elif dists[group] == 't':
                df = pm.Exponential('df', lam=1)
                obs = pm.StudentT('obs', nu=df, mu=loc, sigma=scale,
                                  observed=steps.loc[group])
            else:
                raise NotImplemented(
                    f"Chosen distribution {dists[group]} has not been"
                    f"implemented in `infer_distribution_shapes`"
                )

            trace = pm.sample(**sample_kwargs)

        logger.info(pm.summary(trace))
        parameters = pm.trace_to_dataframe(trace).mean()
        shapes.append(parameters)

    shapes = pd.DataFrame(shapes, index=groups).assign(dist=dists)
    if create_plots:
        plot_distributions_and_hist(shapes, steps)

    return shapes

def plot_distribution_and_hist(shapes, steps=None, file=None):
    distributions = get_distributions_from_shapes(shapes)

    fig, axes = plt.subplots(2, 3, figsize=(12, 8), constrained_layout=True)
    axiter = axes.flat
    x = np.linspace(-1, 1, 500)

    distributions.iloc[0].kwds
    for group in distributions.index:
        ax = next(axiter)
        distribution = distributions.loc[group]
        params_label = ",\n     ".join(f"{k}={v:.4f}" for k,v in distribution.kwds.items())
        dist_label = f"{shapes.loc[group, 'dist'].upper()} ({params_label})"

        ax.plot(x, distribution.pdf(x), label=dist_label)
        if steps is not None:
            sns.distplot(steps, kde=False, norm_hist=True, ax=ax)
        ax.legend()
        ax.set_title(group)

    if file is not None:
        fig.savefig(file)

    return fig

def get_fixed_distribution(dist, **params):
    try:
        return {'al': asymmetric_laplace, 't': scipy.stats.t}[dist](**params)
    except KeyError:
        raise NotImplemented(
            f"Chosen distribution {dist} has not been defined in"
            f"implemented in `get_distributions_from_shapes`"
        )

def get_distributions_from_shapes(shapes):
    return pd.Series([get_fixed_distribution(**v.dropna())
                      for (i,v) in shapes.iterrows()], shapes.index)

def get_distributions(
    shape_parameters_file=Path("shapes.csv"),
    total_cloud_cover_file=Path("tcc.nc"),
    distribution_plots_file=Path("img") / "distributions.png"
):

    if shape_parameter_file.exists():
        shapes = pd.read_csv(shape_parameter_file, index_col=[0, 1])
        shapes.index = pd.IntervalIndex.from_tuples(shapes.index)
    else:
        total_cloud_cover = Path.cwd() / ".." / "munich_tcc.nc"
        lat, lon = 48.12, 11.60

        tcc = get_total_cloud_cover(lon, lat, total_cloud_cover)

        # Split into manually determined bins and compute differences (steps) taken
        # from there
        group_labels = pd.cut(tcc, bins=[-2e-4, -1.0, -1.2, -1.6, -1.8, -1.98, 0.])
        steps = ((tcc.shift(-2) - tcc)
                 .groupby(group_labels)
                 .apply(lambda s: pd.Series.reset_index(s, drop=True))
                 .dropna())
        groups = pd.IntervalIndex(steps.index.levels[-1])
        shapes = infer_distributions(groups, steps, tcc, draws=8000, tune=8000)

        distribution_plots_file = None
        plot_distribution_and_hist(shapes, steps, distribution_plots_file)

        (shapes.set_index(pd.MultiIndex.from_tuples(shapes.index.to_tuples()))
               .to_csv(shape_parameter_file))

    shapes = shapes.rename(columns={'nu': 'df'})
    distributions = get_distributions_from_shapes(shapes)
