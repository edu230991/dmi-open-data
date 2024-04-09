# DMI Open Data API

Simple Python interface to the The Danish Meteorological Institute's (DMI) v2 [Open Data API](https://opendatadocs.dmi.govcloud.dk/en/DMIOpenData).

Forked from [this repo](https://github.com/LasseRegin/dmi-open-data) to add support for more data sources as well as pandas output.

Currently the following APIs are supported:
- climateDataAPI
- forecastedr
- metObsAPI

See API status [here](https://statuspage.freshping.io/25721-DMIOpenDatas)

## Requirements

- Python 3.9+
- API Keys for the different Open Data APIs: see https://dmiapi.govcloud.dk/#!/apis

## Installation

```bash
$ pip install dmi-open-data-pandas
```

## Examples
### Forecast API
```python
from dmi_open_data import DMIOpenDataClient

# initialize client with API key stored in env variable
client = DMIOpenDataClient(env_var_name="DMI_FORECAST_EDR_API_KEY")

# get list of models available
models = client.get_models(as_df=True)

# get info about a specific model
model_info = client.get_models("harmonie_dini_sf")

# list parameters available for specific model
params = client.list_model_parameters("harmonie_dini_sf", as_df=True)

# get a forecast for wind speed and temperature
fc = client.get_forecast(
    latitude=55.767247, 
    longitude=12.464263,
    parameter=["temperature-0m", "wind-speed-10m"]
)
```

### Observations and Climate Data API
```python
from dmi_open_data import DMIOpenDataClient, Parameter, ClimateDataParameter
from datetime import datetime
import pandas as pd

# initialize client with API key stored in env variable
client = DMIOpenDataClient(env_var_name="DMI_API_KEY")

# get all stations
stations = client.get_stations()

# get station closest to a lat-lon
closest_station = client.get_closest_station(
    latitude=55.767247, 
    longitude=12.464263,
)

# Get available parameters
parameters = client.list_observation_parameters()

# Get temperature observations from DMI station in given time period
observations = client.get_observations(
    parameter=Parameter.TempDry,
    station_id=closest_station['properties']['stationId'],
    from_time=datetime(2021, 7, 20),
    to_time=datetime(2021, 7, 24),
    limit=1000
)

# you can also use the simple parameter string, and ask to return a pandas dataframe
observations = client.get_observations(
    parameter="temp_dry",
    station_id=closest_station['properties']['stationId'],
    from_time=datetime(2021, 7, 20),
    to_time=datetime(2021, 7, 24),
    as_df=True
)

# initialize climate data client
climate_data_client = DMIOpenDataClient(env_var_name='DMI_CLIMATE_DATA_API_KEY')

# get climate data, also using pandas Timestamps
climate_data = climate_data_client.get_climate_data(
    parameter=ClimateDataParameter.MeanTemp,
    station_id=closest_station['properties']['stationId'],
    from_time=pd.Timestamp("2023-01-01"),
    to_time=pd.Timestamp("2023-01-03"),
    time_resolution='day',
    as_df=True
)
```

## Tests

Run tests (after installing pytest)

```bash
$ python -m pytest
```

## Contributing
Please send an email to edu230991@gmail.com. We welcome contributions!