import pandas as pd
import numpy as np

from tmhpvsim.pvmodel import PVModel

def test_pvmodel():
    times = pd.date_range("2019-09-05 00:00", "2019-09-06 00:00", freq="s").to_pydatetime()
    pvmodel = PVModel(times[0])
    generation = np.asarray([pvmodel.next(time) for time in times])
    assert (generation >= 0).all()
