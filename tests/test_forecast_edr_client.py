import os
import pytest
import pandas as pd

from dmi_open_data import DMIOpenDataClient


@pytest.fixture
def client():
    return DMIOpenDataClient(api_key=os.getenv("DMI_FORECAST_EDR_API_KEY"))


@pytest.mark.parametrize(
    "as_df,parameter,from_time,to_time",
    [
        (True, "temperature-0m", None, None),
        (False, "temperature-0m", None, None),
        (
            True,
            ["temperature-0m", "wind-dir"],
            pd.Timestamp("now", tz="UTC") + pd.to_timedelta("6h"),
            None,
        ),
        (
            True,
            ["temperature-0m", "wind-dir"],
            (pd.Timestamp("now", tz="UTC") + pd.to_timedelta("6h")).to_pydatetime(),
            None,
        ),
        (
            True,
            ["temperature-0m", "wind-dir"],
            None,
            pd.Timestamp("now", tz="UTC") + pd.to_timedelta("12h"),
        ),
    ],
)
def test_forecast(as_df, parameter, from_time, to_time, client):
    fc_data = client.get_forecast(
        latitude=55.767247,
        longitude=12.464263,
        parameter=parameter,
        as_df=as_df,
        from_time=from_time,
        to_time=to_time,
    )
    assert len(fc_data) > 0
    if as_df:
        assert isinstance(fc_data, pd.DataFrame)

        if from_time is not None:
            assert (fc_data.index >= from_time).all()
        if to_time is not None:
            assert (fc_data.index <= to_time).all()


@pytest.mark.parametrize(
    "model,as_df", [(None, True), (None, False), ("harmonie_dini_sf", False)]
)
def test_get_models(model, as_df, client):
    models = client.get_models(model, as_df)
    if model is not None:
        assert isinstance(models, dict)
    if as_df:
        assert isinstance(models, pd.DataFrame)
    else:
        assert len(models) > 0


@pytest.mark.parametrize("as_df", [True, False])
def test_list_model_params(as_df, client):
    params = client.list_model_parameters("harmonie_dini_sf", as_df)
    assert len(params)
    if as_df:
        assert isinstance(params, pd.DataFrame)


def test_get_model_instances(client):
    instances = client.get_model_instances("harmonie_dini_sf")
    assert len(instances)
