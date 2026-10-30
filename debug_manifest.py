import pandas as pd
df = pd.read_csv('temp_test_manifest.csv')
print('Columns:', df.columns.tolist())
print(df.head())
