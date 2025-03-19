import requests
import pandas as pd
from datetime import datetime, timedelta, timezone
import numpy as np
from predict_valuesinput import PerfPrec

# Get the current date and time in UTC
now_utc = datetime.now(timezone.utc)
# Format the date and time as a string
form_date = now_utc.strftime("%Y%m%d")  # ("%Y-%m-%d %H:%M:%S UTC")
# Define the API endpoint for NWS weather stations
stations_st = "https://api.weather.gov/stations"
stations_url = "https://api.weather.gov/gridpoints/{wfo}/{x},{y}/stations"
states = ['LA', 'AK']  # 'CA', 'MA', 'VA',
# Define the state code for Virginia
# state_code = "VA"


class QryApi:
    """ Query National Weather Service API for weather data related to input parameters, State and weather stations
    :param - state
    :param - stations:
    :returns: current weather extracted from the APIs.  """

    def __init__(self, ec2_ids, indata, state_code):
        self.ec2_ids = ec2_ids
        self.indata = indata
        self.state_code = state_code

    @classmethod
    def gen_randvals(cls, indf):
        # update an existing df with precip data, if none, Load the CSV file into a DataFrame
        if indf.empty:
            input_csv_path = 'weather_obs.csv'
            indf = pd.read_csv(input_csv_path)

        # Determine the number of rows
        num_rows = indf.shape[0]

        # Generate random values with 60% zeros and 40% random integers between 1 and 100
        random_values = np.zeros(num_rows)
        non_zero_count = int(num_rows * 0.40)
        random_values[:non_zero_count] = np.random.randint(1, 101, non_zero_count)

        # Shuffle the array to mix zeros and random values
        np.random.shuffle(random_values)

        # Add the random values as a new column to the DataFrame
        indf['precipitation'] = random_values  # np.ma.array(indf['wind_speed']).anom()
        # windAnom = PerfPrec.decision_localoutlier(indf['wind_speed'].tolist())  # need 2D array for X?
        # indf['anomalies_wind'] = PerfPrec.decision_localoutlier(windAnom)

        # Save the updated DataFrame back to a CSV file
        output_csv_path = f'weather_obs_precip{form_date}.csv'
        # indf.to_csv(output_csv_path, index=False)

        print(f"Random values added to 'random_values' column and saved to {output_csv_path}")
        return indf

    @classmethod
    def fetch_stations(cls, state_code):
        # Function to fetch stations by state, top 5. # attach to reqs, cert="C:\\temp\\cacert-plus.pem"
        if state_code:
            response = requests.get(stations_st, params={"state": state_code, "limit": 5})

        else:
            x, y = 30, 82  # Example: https://api.weather.gov/gridpoints/JAX/30,82/stations
            response = requests.get(f"https://api.weather.gov/gridpoints/JAX/{x},{y}/stations")
        response.raise_for_status()
        data = response.json()
        stations = data['features']
        print('Num Stations: ', len(stations))
        return [station['properties']['stationIdentifier'] for station in stations][0:5]

    @classmethod
    # Function to fetch observations for a station in a given date range
    def fetch_observations(cls, state_code, station_id, start_date, end_date):  # expect time: format YYYY-MM-DDThh:mm:ssZ
        try:
            def convert_epoch_to_utm(epoch_time):
                # Convert the epoch time to a datetime object
                dt_object = datetime.utcfromtimestamp(epoch_time)
                # Format the datetime object to a string in UTM format
                utm_time = dt_object.strftime("%Y-%m-%dT%H:%M:%SZ")  # print('aaaa ', utm_time)
                return utm_time

            # observations_url = f"https://api.weather.gov/stations/{station_id}/observations
            # convert datetime object to string utm t/z format
            end_date = end_date.strftime('%Y-%m-%dT%H:%M:%SZ')
            start_date = start_date.strftime('%Y-%m-%dT%H:%M:%SZ')
            observations_url = f"https://api.weather.gov/stations/{station_id}/observations"  # /{end_date}"
            response = requests.get(observations_url, params={"start": start_date, "end": end_date})
                                    # verify=r"C:\Users\jvonholle\AppData\Local\.certifi\cacert.pem")
            response.raise_for_status()
            data = response.json()
            print('length of features: ', len(data['features']))
            observations = data['features']
            if len(observations) > 0 and 'precipitationLast3Hours' in list(observations[0]['properties'].keys()):
                return [
                    {
                        "state_code": state_code,
                        "station_id": station_id,
                        "timestamp": obs['properties']['timestamp'],
                        "temperature": obs['properties']['temperature']['value'],
                        "wind_speed": obs['properties']['windSpeed']['value'],
                        "precipitation": obs['properties']['precipitationLast3Hours']['value'],
                        "geometry": obs['geometry'],
                        "latitude": obs['geometry']['coordinates'][1],
                        "longitude": obs['geometry']['coordinates'][0],
                    }
                    for obs in observations
                ]
        except Exception as e:
            print(e)
            pass

    @classmethod
    def time_iterweek(cls):
        trang = []
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)  # days=365
        print(start_date)
        print('start')
        current_date = start_date
        while current_date < end_date:
            next_date = current_date + timedelta(days=7)  # Approximate month duration
            # print('Is this happening: ', current_date, next_date)
            trang.append((current_date, next_date))
            current_date = next_date
        return trang

    @classmethod
    def main(cls, state_code):
        # Get the list of stations
        stations = QryApi.fetch_stations(state_code)

        # Define the date range for the past year
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)  # testend = end_date - timedelta(days=7)

        # Create a DataFrame to store all observations
        all_observations = pd.DataFrame()

        # Iterate through each station and fetch observations month by month
        for i, station in enumerate(stations):
            print('extr str end: ', start_date, end_date)  # NO HISTORICAL DATA
            # observations = PerfPrec.fetch_observations(station, start_date, end_date)
            observations = QryApi.fetch_observations(state_code, station, start_date, end_date)

            if observations:  # and i < 20:
                df = pd.DataFrame(observations)
                all_observations = pd.concat([all_observations, df], ignore_index=True)
            else:
                break
            # current_date = next_date  2024-07-07T08:35:00+00:00  2024-07-06T13:35:00+00:00

        # Export the data to a CSV file
        all_observations.to_csv(f"weather_obs_{form_date}.csv", mode='a', index=False)
        # if no precipitation values returned, create some fake ones and gen. new df.

        empty_precip = all_observations.precipitation.isnull().sum()  # if (df['A'] > 1) & (df['B'] < 5):
        print(type(empty_precip), empty_precip)  # fill nulls with int

        if int(empty_precip) > 5:  # pd.Series(empty_precip).empty:  #  or all_observations['precipitation'] == '':
            all_observations = QryApi.gen_randvals(all_observations)

        print("Weather observations exported to 'virginia_weather_observations.csv'")
        return all_observations

    @classmethod
    def multistates(cls):
        # Create a DataFrame to store all observations
        all_observations = pd.DataFrame()
        for state_code in states:
            # Get the list of stations
            stations = QryApi.fetch_stations(state_code)

            # Define the date range for the past year
            end_date = datetime.now()
            start_date = end_date - timedelta(days=7)  # testend = end_date - timedelta(days=7)

            # Iterate through each station and fetch observations month by month
            for i, station in enumerate(stations):
                print('extr str end: ', start_date, end_date)  # NO HISTORICAL DATA
                # observations = PerfPrec.fetch_observations(station, start_date, end_date)
                observations = QryApi.fetch_observations(state_code, station, start_date, end_date)

                if observations:  # and i < 20:
                    df = pd.DataFrame(observations)
                    all_observations = pd.concat([all_observations, df], ignore_index=True)
                else:
                    break
                # current_date = next_date  2024-07-07T08:35:00+00:00  2024-07-06T13:35:00+00:00
        print('check allobser:::', all_observations.shape[0])
        # if no precipitation values returned, create some fake ones and gen. new df.
        empty_precip = all_observations.precipitation.isnull().sum()  # if (df['A'] > 1) & (df['B'] < 5):
        print(type(empty_precip), empty_precip)  # fill nulls with int

        if int(empty_precip) > 5:  # pd.Series(empty_precip).empty:  #  or all_observations['precipitation'] == '':
            all_observations = QryApi.gen_randvals(all_observations)

        # Export the data to a CSV file
        all_observations.to_csv("weather_obs_multi.csv", index=False)

        print("Weather observations exported to 'multistate.csv'")
        return all_observations


if __name__ == '__main__':
    QryApi.multistates()
