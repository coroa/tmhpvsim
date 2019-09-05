import pytz
import datetime
import numpy as np
import pandas as pd

import pvlib
from pvlib.pvsystem import LocalizedPVSystem

from .clearskyindexmodel import ClearskyindexModel

class PVModel:
    def __init__(self, time=None):
        sandia_modules = pvlib.pvsystem.retrieve_sam('SandiaMod')
        module = sandia_modules["Hanwha_HSL60P6_PA_4_250T__2013_"]

        sapm_inverters = pvlib.pvsystem.retrieve_sam("CECInverter")
        inverter = sapm_inverters['ABB__MICRO_0_25_I_OUTD_US_208_208V__CEC_2014_']

        self.tz = pytz.timezone("Europe/Berlin")
        latitude = 48.12

        self.system = LocalizedPVSystem(module_parameters=module,
                                        inverter_parameters=inverter,
                                        surface_tilt=latitude,
                                        surface_azimuth=180,
                                        latitude=latitude,
                                        longitude=11.60,
                                        name="unnamed",
                                        altitude=34,
                                        tz=self.tz)

        if time is None:
            time = datetime.datetime(*datetime.datetime.now().timetuple()[:6])
        self.clearskyindexmodel = ClearskyindexModel(time)
        self.cache = pd.Series(index=pd.DatetimeIndex([], tz=self.tz))
        self.populate_cache(time)

    def populate_cache(self, from_time):
        from_time = pd.Timestamp(from_time, tz=self.tz)
        cache = self.cache.loc[from_time:]
        if len(cache) > 0:
            from_time = cache.index[-1] + pd.Timedelta(seconds=1)

        system = self.system
        times = pd.date_range(from_time, periods=5000, freq="s", tz=self.tz)

        clearskyindex = pd.Series([self.clearskyindexmodel.next(t)
                                   for t in times.to_pydatetime()], times)

        solar_position = system.get_solarposition(times)

        theta = np.radians(solar_position['zenith'])
        clearskyindex = np.clip(
            clearskyindex,
            a_min=None,
            a_max=(27.21 * np.exp(-114*np.cos(theta)) +
                   1.665 * np.exp(-4.494 * np.cos(theta)) + 1.08)
        )

        ghi_clearsky = system.get_clearsky(times, solar_position=solar_position)['ghi']

        ghi = clearskyindex * ghi_clearsky
        dni = pvlib.irradiance.disc(ghi, solar_position['zenith'], times)['dni']
        dhi = ghi - dni * np.cos(theta)

        total_irrad = system.get_irradiance(solar_position['apparent_zenith'],
                                            solar_position['azimuth'],
                                            dni, ghi, dhi)
        temps = system.sapm_celltemp(total_irrad['poa_global'],
                                     wind=0, temp=20)
        aoi = system.get_aoi(solar_position['apparent_zenith'],
                            solar_position['azimuth'])
        airmass = system.get_airmass(solar_position=solar_position)
        effective_irradiance = system.sapm_effective_irradiance(
            total_irrad['poa_direct'], total_irrad['poa_diffuse'],
            airmass['airmass_absolute'], aoi)
        dc = system.sapm(effective_irradiance, temps['temp_cell'])
        ac = system.snlinverter(dc['v_mp'], dc['p_mp'])

        self.cache = cache.append(ac.clip(lower=0.).fillna(0.))

    def next(self, time):
        time_tz = pd.Timestamp(time, tz=self.tz)
        i = self.cache.index.searchsorted(time_tz)
        if i > 0.9 * self.cache.size:
            self.populate_cache(time)
        return self.cache.loc[time_tz]
