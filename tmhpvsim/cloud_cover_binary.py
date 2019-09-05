import numpy as np
import logging
logger = logging.getLogger(__name__)

def random_windspeed(size=None):
    """Draw a random value for the current windspeed

    Returns
    -------
    windspeed : float
        in units of m/s

    Note
    ----
    Assumes windspeeds are distributed as Gamma(2.69, 2.14), as proposed (for
    wind speeds above 1km of the ground) by

    Mathiesen, P., Collier, C., Kleissl, J., 2013. A high-resolution,
    cloud-assimilating numerical weather prediction model for solar
    irradianceforecasting. Sol. Energy 92, 47–61.
    """

    return np.random.gamma(2.69, 2.14)

def random_cloudlength_in_s(windspeed, shape=(1,)):
    """Determine length of `shape` clouds

    Note
    ----
    Cloud length has P(x) ~ x**(-beta) for x in [0.1, 1000] km with beta = 1.66

    Wood, R., Field, P.R., 2011. The distribution of cloud horizontal sizes.
    J.Clim. 24, 4800–4816.
    """
    beta = 1.66
    xmin, xmax = 0.1e3, 1e6
    alpha = xmax**(1-beta)
    delta = xmin**(1-beta) - alpha

    return (alpha + delta * np.random.random(shape))**(1/(1-beta)) / windspeed

class CloudCoverBinary:
    """Generates a binary for each second whether the sky is clear (0) or
    clouded (1).

    Usage
    -----
    ccbin = CloudCoverBinary(hourly_cloudcover)
    iscovered = next(ccbin)
    [...]
    # Update parameters when new ones become available
    ccbin.update_parameters(hourly_cloudcover)
    iscovered = next(ccbin)

    Note
    ----
    The series is ensured to be consistent with
    - the cloud length statistic described in `random_cloudlength_in_s` for a
      given `windspeed`, and
    - the average `hourly_cloudcover`, ie.
      ``mean(b_i for i in last_hour) = hourly_cloudcover``
    """
    def __init__(self, hourly_cloudcover, windspeed=None):
        self.update_parameters(hourly_cloudcover, windspeed)
        self.reset_sigma()
        self.next_cloud()
        # Start somewhere within the first cloud
        self.sec = int((self.cloud_length + self.clear_length) * np.random.random())

    def update_parameters(self, hourly_cloudcover, windspeed=None):
        self.hourly_cloudcover = min(hourly_cloudcover, 0.95)
        if windspeed is None:
            windspeed = get_random_windspeed()
        self.windspeed = windspeed

    def reset_sigma(self):
        self.sigma_cloud = np.cumsum(5 * 60 * np.ones(int(self.hourly_cloudcover*12)))
        self.sigma_clear = (1/self.hourly_cloudcover - 1) * self.sigma_cloud

    def next_cloud(self, recurse=False):
        for i in range(20):
            cloud_length = random_cloudlength_in_s(self.windspeed)
            next_sigma_cloud = cloud_length + self.sigma_cloud
            next_sigma_clear = (1/self.hourly_cloudcover - 1) * next_sigma_cloud

            tot_length = next_sigma_cloud + next_sigma_clear
            possible = (next_sigma_clear - self.sigma_clear > 0) & (tot_length < 90 * 60)
            if possible.any():
                break
        else:
            assert not recurse

            # Re-initialise sigma_cloud and sigma_clear (should never be reached)
            logger.error(f"20 random cloudlengths rejected at windspeed {self.windspeed} "
                         f"and cloudcover {self.hourly_cloudcover}. Re-initialise "
                         "sigma_cloud, sigma_clear. Then re-run.")
            self.reset_sigma()
            return self.next_cloud(recurse=True)

        last = np.nonzero(possible)[0][abs(tot_length[possible] - 60 * 60).argmin()]
        self.cloud_length = cloud_length
        self.sigma_cloud = np.r_[cloud_length, next_sigma_cloud[:last+1]]
        self.clear_length = next_sigma_clear[last] - self.sigma_clear[last]
        self.sigma_clear = np.r_[self.clear_length, next_sigma_clear[:last+1]]
        self.sec = 0

        return self.cloud_length, self.clear_length

    def __next__(self):
        self.sec += 1
        if self.sec < self.cloud_length:
            return 1
        elif self.sec < self.cloud_length + self.clear_length:
            return 0
        else:
            self.next_cloud()
            return next(self)
