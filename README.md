# CloudEvent Viewer

A free, open source in-memory [Cloud Events](https://cloudevents.io) viewer.

## Use The CloudEvent Viewer

Click "Code" > Codespaces > Create codespace on main

When the codespace starts, toggle to the Ports tab and open the application on port 6060.

## Run Locally

```
git clone https://github.com/agardnerit/cloudeventviewer
pip install -r requirements.txt
python app.py

# App is running on http://127.0.0.1:6060
# Configure via config.json and restart app to pick up new configs
```

## The Technical details

This is a flask app that uses an in-memory sqlite3 database.

Filtering is performed via jsonlogic. See [json_logic_samples.txt](json_logic_samples.txt) for examples.
