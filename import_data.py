import requests
import os



base_url = 'https://docs.google.com/spreadsheets/d/1xdJA8uSvUBGFET2Smih_s_desxMj6T8xab158fy79S0/gviz/tq?tqx=out:csv&sheet='

shifts = base_url + 'shifts'
tasks = base_url + 'tasks'

urls = [shifts, tasks]

os.makedirs('data', exist_ok=True)

for url in urls:
    r = requests.get(url)
    file_path = os.path.join('data', url.split('=')[-1] + '.csv')
    with open(file_path, 'wb') as f:
        f.write(r.content)
    print('Downloaded ' + file_path)
