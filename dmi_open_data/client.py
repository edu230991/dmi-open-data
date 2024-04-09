from datetime import datetime, timezone
from typing import List, Dict, Optional, Any, Union
from requests.exceptions import HTTPError

import requests
import os
import pandas as pd

from tenacity import retry, stop_after_attempt, wait_random

from dmi_open_data.enums import Parameter, ClimateDataParameter
from dmi_open_data.utils import distance


class DMIOpenDataClient:
    _base_url = "https://dmigw.govcloud.dk/{version}/{api}"

    def __init__(self, api_key: str = None, env_var_name: str = None):
        """Initializes class

        :param api_key: defaults to None, in which case 'env_var_name' needs to be not None
        :param env_var_name: name of the environment variable in which you stored the API key.
            Defaults to None, in which case 'api_key' needs to be not None.
        :raises ValueError: in case both arguments are None
        """
        if api_key is None:
            api_key = os.getenv(env_var_name)
        if api_key is None:
            raise ValueError("Need to pass an api key or a valid environment variable")
        self.api_key = api_key

    def _get_version(self, api: str) -> str:
        """Returns current version of the API for a given service

        :param api: name of the API
        :return: version number
        """
        if api in ("metObs", "climateData"):
            return "v2"
        else:
            return "v1"

    def base_url(self, api: str) -> str:
        """Gets the base url for the API

        :param api: name of the API
        :return: base url
        """
        version = self._get_version(api)
        return self._base_url.format(version=version, api=api)

    @retry(stop=stop_after_attempt(3), wait=wait_random(min=0.1, max=1.00))
    def _query(self, api: str, service: str, params: Dict[str, Any], **kwargs) -> dict:
        """Queries API for given service

        :param api: name of the API
        :param service: url to be accessed
        :param params: params for the request
        :raises HTTPError: if status code is not 200
        :return: dict with response contents
        """
        res = requests.get(
            url=f"{self.base_url(api=api)}/{service}",
            params={
                "api-key": self.api_key,
                **params,
            },
            **kwargs,
        )
        data = res.json()
        http_status_code = data.get("http_status_code", 200)
        if http_status_code != 200:
            message = data.get("message")
            raise HTTPError(
                f"Failed HTTP request with HTTP status code {http_status_code} and message: {message}"
            )
        return res.json()

    def get_stations(self, limit: int = 10000, offset: int = 0) -> list[dict]:
        """Query the API to obtain a list of stations

        :param limit: maximum number of datapoints to return, defaults to 10000
        :param offset: defaults to 0
        :return: list of dicts with station info
        """

        res = self._query(
            api="metObs",
            service="collections/station/items",
            params={
                "limit": limit,
                "offset": offset,
            },
        )
        return res.get("features", [])

    def get_observations(
        self,
        parameter: Parameter | str = None,
        station_id: int = None,
        from_time: datetime | pd.Timestamp = None,
        to_time: datetime | pd.Timestamp = None,
        limit: int = 10000,
        offset: int = 0,
        as_df: bool = False,
    ) -> list[dict] | pd.DataFrame:
        """Gets data from the MetObsAPI.

        :param parameter: parameter to retrieve, defaults to None
            which returns all parameters for this station
        :param station_id: station ID, defaults to None which returns all stations
        :param from_time: start datetime for data to return. If not localized will be
            considered UTC. Defaults to None in which case all data is returned
            (compatibly with 'limit' and 'offset')
        :param to_time: end datetime for data to return. If not localized will be
            considered UTC. Defaults to None in which case all data is returned
            (compatibly with 'limit' and 'offset')
        :param limit: limit to the number of rows to return, defaults to 10000
        :param offset: offset to the data to apply (from latest datapoint), defaults to 0
        :param as_df: is True, data is returned in dataframe format, defaults to False
        :return: observation data
        """

        res = self._query(
            api="metObs",
            service="collections/observation/items",
            params={
                "parameterId": (
                    parameter.value if isinstance(parameter, Parameter) else parameter
                ),
                "stationId": station_id,
                "datetime": self._construct_datetime_argument(
                    from_time=from_time, to_time=to_time
                ),
                "limit": limit,
                "offset": offset,
            },
        )
        if as_df:
            return self._json_to_df(res, ["created", "observed"])
        else:
            return res.get("features", [])

    def get_climate_data(
        self,
        parameter: ClimateDataParameter | str = None,
        station_id: int = None,
        from_time: datetime | pd.Timestamp = None,
        to_time: datetime | pd.Timestamp = None,
        time_resolution: str = None,
        limit: int = 10000,
        offset: int = 0,
        as_df: bool = False,
    ) -> list[dict] | pd.DataFrame:
        """Gets Climate Data API, potentially in aggregated form. By definition climate data
        is observation data that is of confirmed quality and more than 7 days old.

        :param parameter: parameter to retrieve, defaults to None
            which returns all parameters for this station
        :param station_id: station ID, defaults to None which returns all stations
        :param from_time: start datetime for data to return. If not localized will be
            considered UTC. Defaults to None in which case all data is returned
            (compatibly with 'limit' and 'offset')
        :param to_time: end datetime for data to return. If not localized will be
            considered UTC. Defaults to None in which case all data is returned
            (compatibly with 'limit' and 'offset')
        :param time_resolution: aggregates data.
            One in ('day', 'month', 'year', '10years', '30years'), defaults to None
        :param limit: limit to the number of rows to return, defaults to 10000
        :param offset: offset to the data to apply (from latest datapoint), defaults to 0
        :param as_df: is True, data is returned in dataframe format, defaults to False
        :return: climate data
        """

        res = self._query(
            api="climateData",
            service="collections/stationValue/items",
            params={
                "parameterId": (
                    parameter.value
                    if isinstance(parameter, ClimateDataParameter)
                    else parameter
                ),
                "stationId": station_id,
                "datetime": self._construct_datetime_argument(
                    from_time=from_time, to_time=to_time
                ),
                "timeResolution": time_resolution,
                "limit": limit,
                "offset": offset,
            },
        )
        if as_df:
            return self._json_to_df(res, ["calculatedAt", "created", "from", "to"])
        else:
            return res.get("features", [])

    @staticmethod
    def _json_to_df(res: dict, time_cols: list) -> pd.DataFrame:
        """Turns a json response into a pandas dataframe, transforming
        selcted columns to datetime

        :param res: json response
        :param time_cols: list of columns to transform to datetime
        :return: dataframe
        """
        df = pd.DataFrame([row["properties"] for row in res.get("features", [])])
        for col in time_cols:
            if col in df:
                df[col] = pd.to_datetime(df[col], format="ISO8601")
        return df

    def list_observation_parameters(self, as_df: bool = False) -> list | pd.DataFrame:
        """List all observation parameters

        :param as_df: if true, data is returned as a pandas dataframe, defaults to False
        :return: parameters for observation api
        """
        param_list = [
            {
                "name": parameter.name,
                "value": parameter.value,
                "enum": parameter,
            }
            for parameter in Parameter
        ]
        if as_df:
            param_list = pd.DataFrame(param_list)
        return param_list

    def list_climate_parameters(self, as_df: bool = False) -> list | pd.DataFrame:
        """List all climate data parameters

        :param as_df: if true, data is returned as a pandas dataframe, defaults to False
        :return: parameters for climate data api
        """
        param_list = [
            {
                "name": parameter.name,
                "value": parameter.value,
                "enum": parameter,
            }
            for parameter in ClimateDataParameter
        ]
        if as_df:
            param_list = pd.DataFrame(param_list)
        return param_list

    def list_model_parameters(
        self, model: str, as_df: bool = False
    ) -> list[dict] | pd.DataFrame:
        """Returns a list of available parameters for the specific forecasting model

        :param model: name of model
        :param as_df: if true, data is returned as pandas dataframe, defaults to False
        :return: available model parameters
        """
        model_info = self.get_models(model)
        parameters = model_info["parameter_names"]
        if as_df:
            parameters = pd.DataFrame(parameters).T
        return parameters

    def get_closest_station(self, latitude: float, longitude: float) -> list[dict]:
        """Gets closest weather station to specified lat-lon.

        :param latitude:
        :param longitude:
        :return: station dict with info
        """
        stations = self.get_stations()
        closest_station, closests_dist = None, 1e10
        for station in stations:
            coordinates = station.get("geometry", {}).get("coordinates")
            if coordinates is None or len(coordinates) < 2:
                continue
            lat, lon = coordinates[1], coordinates[0]
            if lat is None or lon is None:
                continue

            # Calculate distance
            dist = distance(
                lat1=latitude,
                lon1=longitude,
                lat2=lat,
                lon2=lon,
            )

            if dist < closests_dist:
                closests_dist, closest_station = dist, station
        return closest_station

    @staticmethod
    def _get_datetime_string(datetime: datetime | pd.Timestamp) -> str:
        """Given a datetime, converts to the right string format

        :param datetime:
        :return: string
        """
        if datetime is not None:
            datetime = pd.Timestamp(datetime).round("ms")
            if datetime.tz is None:
                datetime = datetime.tz_localize("UTC")
            else:
                datetime = datetime.tz_convert("UTC")
            datetime = datetime.tz_localize(None)
            datetime_str = f"{datetime.isoformat(timespec='milliseconds')}Z"
        else:
            datetime_str = ".."
        return datetime_str

    def _construct_datetime_argument(
        self,
        from_time: datetime | pd.Timestamp = None,
        to_time: datetime | pd.Timestamp = None,
    ) -> str:
        """Construct datetime argument following API requirements

        :param from_time: defaults to None
        :param to_time: defaults to None
        :return: string argument
        """

        if from_time is None and to_time is None:
            return None
        from_str = self._get_datetime_string(from_time)
        to_str = self._get_datetime_string(to_time)
        return f"{from_str}/{to_str}"

    def get_models(
        self, model: str = None, as_df: bool = False
    ) -> list | dict | pd.DataFrame:
        """Gets a list of forecasting models available and their information

        :param model: if passed, info is returned only for that model,
            defaults to None in which case all modesl are returned
        :param as_df: if true, data is returned as pandas dataframe, defaults to False
        :return: model info
        """
        res = self._query(
            api="forecastedr",
            service="collections" + ("" if model is None else f"/{model}"),
            params={},
        )
        if model is None:
            res = res.get("collections")
            if as_df:
                res = pd.DataFrame(res)
        return res

    def get_model_instances(self, model: str) -> list[dict]:
        """Gets instances (historical runs) of the model.
        Instance IDs can be used to specify model runs when getting data.

        :param model: model name
        :return: instances
        """
        res = self._query(
            api="forecastedr", service=f"collections/{model}/instances", params={}
        )
        return res

    def get_forecast(
        self,
        latitude: float,
        longitude: float,
        parameter: list[str] = None,
        from_time: datetime = None,
        to_time: datetime = None,
        model: str = "harmonie_dini_sf",
        instance: str = None,
        as_df: bool = True,
    ) -> list[dict] | pd.DataFrame:
        """Queries ForecastEDR API to get prediction data

        :param latitude: latitude of the point
        :param longitude: longitude of the point
        :param parameter: parameter to get data for (see self.list_model_parameters),
            defaults to None in which case all parameters are queried
        :param from_time: start datetime for data to return. If not localized will be
            considered UTC. Defaults to None in which case all data is returned
            (compatibly with 'limit' and 'offset')
        :param to_time: end datetime for data to return. If not localized will be
            considered UTC. Defaults to None in which case all data is returned
            (compatibly with 'limit' and 'offset')
        :param model: model name (see self.get_models), defaults to "harmonie_dini_sf"
        :param instance: instance (i.e. run) for the model (see self.get_model_instances),
            defaults to None in which case the latest instance is used
        :param as_df: if true, data is returuned as pandas dataframe, defaults to True
        :return: forecast data
        """
        if instance is not None:
            model += f"/instances/{instance}"
        if isinstance(parameter, str):
            parameter = [parameter]

        res = self._query(
            api="forecastedr",
            service=f"collections/{model}/position",
            params={
                "coords": f"POINT({longitude} {latitude})",
                "crs": "crs84",
                "parameter-name": ",".join(parameter),
                "f": "CoverageJSON",
                "datetime": self._construct_datetime_argument(from_time, to_time),
            },
        )

        if as_df:
            idx = pd.to_datetime(res["domain"]["axes"]["t"]["values"])
            values = {p: rng["values"] for p, rng in res["ranges"].items()}
            res = pd.DataFrame(values, index=idx)
        return res
