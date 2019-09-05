from scipy.stats import norm, gamma
import numpy as np
from collections import namedtuple

from .cloud_cover_hourly import (
    get_cloud_cover,
    get_distributions_from_shapes_file
)

from .cloud_cover_binary import random_windspeed, CloudCoverBinary

class InterpolatedSampler:
    """
    Encapsulates interpolation between regularly updated random samples

    Parameters
    ----------
    next_sample_func : callable
        Function is called without arguments to get the next sample

    Usage
    -----
    sampler = InterpolatedSampler(lambda: scipy.stats.norm.rvs())
    interpolate(0.25) -> 1/4 * second last sample + 3/4 * last sample
    interpolate(0.5)  -> (second last sample + last sample)/2
    next(sample)
    """

    def __init__(self, next_sample_func):
        self.next_sample_func = next_sample_func
        self.before = next_sample_func()
        self.after = next_sample_func()

    def __next__(self):
        self.before = self.after
        self.after = self.next_sample_func()
        return self.before

    def interpolate(self, fraction):
        return fraction * self.after + (1 - fraction) * self.before

Time = namedtuple('Time', ['time', 'day_fraction', 'hour_fraction', 'min_fraction'])

class ClearskyindexModel:
    """Implements a slightly simplified and streaming version of the model
    described in [1].

    References
    ----------
    [1] Bright, J. M., Smith, C. J., Taylor, P. G., & Crook, R. (2015).
    Stochastic generation of synthetic minutely irradiance time series derived
    from mean hourly weather observation data. Solar Energy, 115, 229-242.

    """
    time = None

    def __init__(self, time):
        self._set_time(time)

        distributions = get_distributions_from_shapes_file()
        self.cloudcover_hour = InterpolatedSampler(
            lambda: next(get_cloud_cover(distributions))
        )
        self.clearskyindex_clear_day = InterpolatedSampler(
            lambda: norm.rvs(loc=0.99, scale=0.08)
        )

        def next_sample_clearskyindex_cloudy():
            cc = self.cloudcover_hour.interpolate(self.time.hour_fraction)
            if cc < 6/8:
                return norm.rvs(loc=0.6784, scale=0.2046)
            elif cc < 7/8:
                # Paper proposed Weibull distribution, but mean and max value
                # of PDF don't coincide with shown plot. Pbb another
                # parametrisation or oversight by the authors

                #   return exponweib.rvs(a=0.5577, c=2.4061)

                # instead we use a visually fitted gamma distribution
                return gamma.pdf(x, a=5, scale=0.1)
            else:
                return gamma.rvs(a=3.5624, scale=0.0867)

        self.clearskyindex_cloudy_hour = InterpolatedSampler(next_sample_clearskyindex_cloudy)

        def scaled_normal_with_cloudcover(sigma0, sigma1):
            cc = self.cloudcover_hour.interpolate(self.time.hour_fraction)
            return norm.rvs(loc=1., scale=np.sqrt(0.9) * (sigma0 + sigma1 * 8 * cc))

        self.clearskyindex_cloudy_noise_min = InterpolatedSampler(
            lambda: scaled_normal_with_cloudcover(0.01, 0.003)
        )
        self.clearskyindex_clear_noise_min = InterpolatedSampler(
            lambda: scaled_normal_with_cloudcover(0.001, 0.0015)
        )

        self.windspeed_day = InterpolatedSampler(lambda: random_windspeed())
        self.cloudcover_binary = CloudCoverBinary(self.cloudcover_hour.interpolate(0),
                                                  self.windspeed_day.interpolate(0))

    def _next_day(self):
        next(self.clearskyindex_clear_day)
        next(self.windspeed_day)

    def _next_hour(self):
        next(self.cloudcover_hour)
        next(self.clearskyindex_clear_day)

    def _next_min(self):
        next(self.clearskyindex_cloudy_noise_min)
        next(self.clearskyindex_clear_noise_min)

    def _set_time(self, time):
        min_fraction = time.second / 60
        hour_fraction = (time.minute + min_fraction) / 60
        day_fraction = (time.hour + hour_fraction) / 24
        prev_time = self.time.time if self.time is not None else None
        self.time = Time(time, day_fraction, hour_fraction, min_fraction)

        if prev_time is not None:
          if prev_time.day != time.day:
              self._next_day()
          if prev_time.hour != time.hour:
              self._next_hour()
          if prev_time.minute != time.minute:
              self._next_min()

    def next(self, time):
        self._set_time(time)

        cloudcover = self.cloudcover_hour.interpolate(self.time.hour_fraction)

        self.cloudcover_binary.update_parameters(
            hourly_cloudcover=self.cloudcover_hour.interpolate(self.time.hour_fraction),
            windspeed=self.windspeed_day.interpolate(self.time.day_fraction)
        )
        covered = bool(next(self.cloudcover_binary))

        # Deviating from the paper, we split the normally distributed white
        # noise with minute-resolution into two separate noise processes, one
        # with minute resolution and one with second resolution.
        # We use the assumption that per-second process makes up a tenth of the
        # averaged per-hour noise =>
        #   sigma_min = sqrt(0.9) * sigma_paper,
        #   sigma_sec = sqrt(0.1 * 60) * sigma_paper
        def normal_with_cloudcover_sec(sigma0, sigma1):
            return norm.rvs(scale=np.sqrt(0.1 * 60) * (sigma0 + sigma1 * 8 * cloudcover))

        if covered:
            csi_day = self.clearskyindex_clear_day.interpolate(self.time.day_fraction)
            csi_noise_min = self.clearskyindex_clear_noise_min.interpolate(self.time.min_fraction)
            csi_noise_sec = normal_with_cloudcover_sec(0.001, 0.0015)

            return csi_day * (csi_noise_min + csi_noise_sec)
        else:
            csi_hour = self.clearskyindex_cloudy_hour.interpolate(self.time.hour_fraction)
            csi_noise_min = self.clearskyindex_cloudy_noise_min.interpolate(self.time.min_fraction)
            csi_noise_sec = normal_with_cloudcover_sec(0.001, 0.0015)

            return csi_hour * (csi_noise_min + csi_noise_sec)
