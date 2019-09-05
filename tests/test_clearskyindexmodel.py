import pandas as pd
import numpy as np
import tmhpvsim

from tmhpvsim.clearskyindexmodel import ClearskyindexModel

def test_clearskyindexmodel():
    times = pd.date_range("2019-09-05 12:00", "2019-09-06 13:00", freq="s").to_pydatetime()
    clearskyindexmodel = ClearskyindexModel(times[0])

    clearskyindex = np.asarray([clearskyindexmodel.next(time) for time in times])

    assert (clearskyindex > 0).all() and (clearskyindex < 2).all()
