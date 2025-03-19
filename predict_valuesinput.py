import pandas as pd
from datetime import datetime, timedelta, timezone
from sklearn.linear_model import LinearRegression, ARDRegression  # try autoregression > best for predicts.
from sklearn.neighbors import LocalOutlierFactor
from sklearn.model_selection import train_test_split, TimeSeriesSplit
from sklearn.preprocessing import StandardScaler

# Format the date and time as a string
form_date = datetime.now(timezone.utc).strftime("%Y%m%d")


class PerfPrec:
    """ Script will est. a process to get ec2 instance issues with the aws inspector by:
        - create assessment template, - start assessment run, - get assessment report
    :param - instance ids/arns
    :param - index (str): ES Index
    :returns: - list of geojson features: the results contain properties extracted from the APIs.  """

    def __init__(self, ec2_ids, df):
        self.ec2_ids = ec2_ids
        self.df = df
        # self.ssm_client = ssm_client

    @staticmethod
    def anom_detect(df, y):
        # input existing df and single column df of values to determine anomalies
        model_LOF = LocalOutlierFactor()
        LOF_predictions = model_LOF.fit_predict(y)

        model_LOF_scores = model_LOF.negative_outlier_factor_

        df['LOF_anomaly_scores'] = model_LOF_scores

        df['LOF_anomaly'] = LOF_predictions
        return df

    @classmethod
    def decision_localoutlier(cls, X):
        clf = LocalOutlierFactor(n_neighbors=20, contamination=0.1)
        y_pred = clf.fit_predict(X)
        # n_errors = (y_pred != ground_truth).sum()
        X_scores = clf.negative_outlier_factor_
        print(y_pred, X_scores)
        return y_pred

    @classmethod
    def linear_regr(cls, indic):
        # Perform time series Linear Regression to predict values from historical data.
        df = pd.DataFrame.from_dict(indic)  # .read_csv('weather_observations.csv')
        # filter df by four time periods per day, Extract the hour from 'datetime' column
        # Ensure 'timestamp' column is in datetime format and convert to UTC
        df['timestamp'] = pd.to_datetime(df['timestamp']).dt.tz_convert('UTC')
        df['hour'] = df['timestamp'].dt.hour
        df['dayofweek'] = df['timestamp'].dt.dayofweek
        # get unique hours value, take first one...  # df = df.drop_duplicates(subset=['dayofweek', 'hour'])
        print(df.head())

        # Split data // THE TEST DATA NEEDS TO BE THE LATER PART BY TIME OF THE DATASET. SEE BELOW.
        X = df[['dayofweek', 'hour']]
        print('X: ', X[200:220])
        df['precipitation'] = df['precipitation'].fillna(0)
        y = df['precipitation']
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)

        # Feature scaling
        scaler = StandardScaler()
        X_train = scaler.fit_transform(X_train)
        X_test = scaler.transform(X_test)

        # Train model
        model = LinearRegression()
        model.fit(X_train, y_train)

        # Make predictions
        y_pred = model.predict(X_test)
        print('Predictions: ', y_pred)
        # OUTPUT PREDICTED VALUES TO DASH PLOT
        df['predictions'] = y_pred
        # Export the data to a CSV file
        df.to_csv("weather_obs_wpred.csv", index=False)

    @classmethod
    def linear_regr_timeseries(cls, df=None):
        # Perform time series Linear Regression to predict values from historical data, Load the data
        if df is None:
            df = pd.read_csv('weather_obs_addprecip.csv')
        # filter df by four time periods per day, Extract the hour from 'datetime' column
        # Ensure 'timestamp' column is in datetime format and convert to UTC
        df['timestamp'] = pd.to_datetime(df['timestamp']).dt.tz_convert('UTC')
        df['dayofweek'] = df['timestamp'].dt.dayofweek
        df['hour'] = df['timestamp'].dt.hour
        # get unique hours value, take first one...  # df = df.drop_duplicates(subset=['dayofweek', 'hour'])
        print(df.head())

        # Create a TimeSeriesSplit object
        tscv = TimeSeriesSplit(n_splits=3)

        # Set df index to time; prepare X, features, and y target as data series; use reset_index() 1st to retain timest
        df.reset_index().set_index('timestamp', inplace=True)
        df.sort_index(inplace=True)
        X = df[['dayofweek', 'hour']]
        print(X[5:15])  # X = df.drop(labels=['precipitation'], axis=1)
        # pass the X to local outlier factor
        PerfPrec.decision_localoutlier(X)

        # Split data // THE TEST DATA NEEDS TO BE THE LATER PART BY TIME OF THE DATASET. SEE BELOW.
        df['temperature'] = df['temperature'].fillna(0)  # precipitation | temperature
        y = df['temperature']

        # X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)

        # Split the data into train and test sets
        for train_index, test_index in tscv.split(X):
            X_train, X_test = X.iloc[train_index], X.iloc[test_index]
            y_train, y_test = y.iloc[train_index], y.iloc[test_index]

        # Feature scaling; scale the data to avoid continuous rise from linear regression.
        scaler = StandardScaler()
        X_train = scaler.fit_transform(X_train)
        X_test = scaler.transform(X_test)

        # Train model
        model = LinearRegression()
        model.fit(X_train, y_train)

        # Make predictions; [day, hour], day 1 and hour 5, etc. Use day/hour from training data for prediction
        train_array = df[['dayofweek', 'hour']].values
        train_scl = scaler.transform(train_array)
        y_pred = model.predict(train_scl)  # X_test
        print('Predictions: ', y_pred)
        df['predict_nextweek'] = y_pred
        df['predict_nextweek'] = df['predict_nextweek'].apply(lambda x: round(x, 2))
        # add anomaly detection for a spec column of data.
        updf = PerfPrec.anom_detect(df, df.loc[:, ['temperature']])  # anom inp needs single col df
        if not updf.empty:
            df = updf

        # Export the data to a CSV file
        df.to_csv(f"weather_obs_wpred_{form_date}.csv", mode='a', index=False)  # df.to_csv(‘existing.csv’, mode=’a’, index=False, header=False)
        return df


# if __name__ == '__main__':
#     PerfPrec.linear_regr_timeseries()
