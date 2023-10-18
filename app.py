from flask import request, Flask, render_template
import logging as logger
import uuid
from datetime import datetime, timezone
import sqlite3
import json
from json_logic import jsonLogic
import os

load_demo_data = True # TODO move to env var
DEFAULT_TZ = timezone.utc
data_filter = "ALL"

# Usage
# Note: MacOS post 5000 is used. Pick 5002 instead
# flask --app=app run --host 0.0.0.0 --port 5002
# curl -X POST http://localhost:5002/insert -H 'Content-Type: application/json' -d '{"type": "pipeline.started"}'

app = Flask(__name__)
app.config.from_file(filename="config.json", load=json.load)

# Demo Data
ce_order = app.config['DEFAULT_CLOUD_EVENT_ORDER']

logger.basicConfig(level=app.config['MIN_LOG_LEVEL'])

# Initialise DB
db_connection = sqlite3.connect(":memory:", check_same_thread=False)
db_connection.row_factory = sqlite3.Row
cursor = db_connection.cursor()
cursor.execute("CREATE TABLE json (id text primary key, event json);")

# Basic validation of cloudevent
def is_valid_cloudevent(document):
    # logger.info("validating CE...")
    # logger.info(type(document))
    if "id" in document and "type" in document and "time" in document and "specversion" in document and "source" in document: return True
    return False

def insert_document(document):
    cursor = db_connection.cursor()

    if isinstance(document, list): # insert multiple records
        for ce in document:
            if is_valid_cloudevent(ce):
                cursor.execute("INSERT INTO json values(?,?)", [ce['id'], json.dumps(ce,)])
    elif isinstance(document, dict): # insert single record
        # insert one
        if is_valid_cloudevent(document):
            cursor.execute("INSERT INTO json values(?,?)", [document['id'], json.dumps(document,)])
        else:
            return "Unexpected input. Input failed. Send JSON object or array."
    else:
        return "Unexpected input. Input failed. Send JSON object or array."
    return "Document(s) Inserted..."

def get_all_data_from_db():
    # Yes, horrible and inefficient
    # But it's a demo / POC system
    # PRs welcome
    query = "SELECT * FROM json"
    cursor = db_connection.cursor()
    rows = cursor.execute(query).fetchall()
    return_list = list()
    for row in rows:
        return_list.append(json.loads(row['event']))
    
    return return_list

def get_cloud_events(filter):

    # logger.info(f"FILTER TYPE IS: {type(filter)}. VALUE IS: {filter}")

    db_items = get_all_data_from_db()

    # if filter is ALL or (probably) an invalid JSON filter
    # eg. the string "foo". Then just be safe and return all items
    # logger.info(f"GOT FILTER TYPE: {type(filter)}")

    if "," in filter:
        # filter contains comma so probably on ordered_flow page
        # only retrieve those types of cloudevents
        return_list = list()
        cloud_event_types_to_retrieve = [x.strip() for x in filter.split(',')]

        logger.info(cloud_event_types_to_retrieve)
        for cloud_event in db_items:
            if cloud_event['type'] in cloud_event_types_to_retrieve:
                return_list.append(cloud_event)
        return return_list

    if filter == "ALL" or (not filter.startswith("[") and not filter.startswith("{")): return db_items

    # If here, the filter is not ALL
    # Or even a CSV
    # So it's a JsonFilter
    matched_rows = list()

    for item in db_items:
        json_logic_rule_obj = json.loads(filter)
        if jsonLogic(json_logic_rule_obj, item):
            # logger.info("GOT A MATCHED ROW!!")
            matched_rows.append(item)
    
    return matched_rows

def create_cloudevent(id=None, type=None, time=None, source=None, specversion=None, datacontenttype=None, data=None, extra_fields=None):

    if id is None or id == "": id = str(uuid.uuid4())
    if type is None or type == "": type = app.config['DEFAULT_CE_TYPE']
    if time is None or time == "": time = str(datetime.now(DEFAULT_TZ))
    if source is None or source == "": source = "cloudeventsviewer-defaultsource"
    if specversion is None or specversion == "": specversion = "1.0"
    if datacontenttype is None or datacontenttype == "": datacontenttype = "application/json"
    if data is None: data = {}

    # CloudEvents     Type                Exemplary JSON Value
    # type            String              "com.example.someevent"
    # specversion	    String	            "1.0"
    # source	        URI-reference	    "/mycontext"
    # subject	        String	            "larger-context"
    # subject	        String (null)	    null
    # id	            String	            "1234-1234-1234"
    # time	        Timestamp	        "2018-04-05T17:31:00Z"
    # time	        Timestamp (null)	null
    # datacontenttype	String	            "application/json"
    # data            object              {"foo": "bar"}
    
    # {
    #     "specversion" : "1.0",
    #     "type" : "com.example.someevent",
    #     "source" : "/mycontext",
    #     "id" : "A234-1234-1234",
    #     "time" : "2018-04-05T17:31:00Z",
    #     "comexampleextension1" : "value",
    #     "comexampleothervalue" : 5,
    #     "unsetextension": null,
    #     "datacontenttype" : "text/xml",
    #     "data" : "<much wow=\"xml\"/>"
    # }

    ce = {
        "specversion": specversion,
        "type": type,
        "source": source,
        "id": id,
        "time": time,
        "datacontenttype": datacontenttype,
        "data": data
    }
    
    # Add any extra fields (if any)
    if extra_fields is not None:
        for key in extra_fields:
            ce[key] = extra_fields[key]

    return ce

@app.route('/', methods=['GET'])
def homepage():
    cloud_events = get_cloud_events(data_filter) # Get all cloudevents from DB
    logger.info(f"Number of Cloud Events: {len(cloud_events)}")

    # for ce in cloud_events: logger.info(ce)

    return render_template('ce_live_flow.html', cloud_events=cloud_events, uri=app.config['HOST'], port=app.config['PORT'], data_filter=data_filter)

@app.route('/ordered_flow', methods=['GET'])
def ordered_flow():
    # logger.info(f"CE Order is: {ce_order}")
    cloud_events = get_cloud_events(ce_order)
    return render_template('ce_ordered_flow.html', cloud_events=cloud_events, uri=app.config['HOST'], port=app.config['PORT'], ce_order=ce_order)

@app.route('/insert', methods=['POST'])
def insert():
    return insert_document(request.json)

@app.route('/update_order', methods=['POST'])
def update_ce_order():
    global ce_order

    if request.method == 'POST':
        # logger.info(f"Update CE Order requested. Got data: {request.data}")
        # logger.info(f"ce_order is originally: {ce_order}")
        data_filter = request.json
        ce_order = data_filter['value']
        # logger.info(f"ce_order is now: {ce_order}")
        return "OK"

@app.route('/load_demo_data', methods=['GET'])
def load_demo_data():

    # First clear demo data to prevent duplicates
    clear_demo_data()

    # Load cloud event skeletons
    # Then create real, full cloud events from those skeletons
    # Finally, load them into the database
    cloud_event_skeletons = app.config['DEFAULT_CLOUD_EVENT_SKELETONS']
    for ce_skel in cloud_event_skeletons:
        ce = create_cloudevent(type=ce_skel['type'], source=ce_skel['source'], data=ce_skel['data'])
        insert_document(ce)

    return "OK"

@app.route('/clear_demo_data', methods=['GET'])
def clear_demo_data():
    global ce_order

    cursor.execute("DELETE FROM json WHERE json_extract(event, '$.data.is_demo_data') = True")

    # reset default ce_order to whatever came from config
    ce_order = app.config['DEFAULT_CLOUD_EVENT_ORDER']
    return "OK"

@app.route('/clear_all_data', methods=['GET'])
def clear_all_data():
    global ce_order
    cursor.execute("DELETE FROM json")
    ce_order = ""
    return "OK"

@app.route("/help", methods=['GET'])
def help_page():
    return render_template("help.html")

@app.route("/build", methods=['GET'])
def builder_page():
    return render_template("ce_builder.html", uri=app.config['HOST'], port=app.config['PORT'])

if __name__ == "__main__":
    if app.config['LOAD_DEMO_DATA']:
        load_demo_data()
    
    app.run(host=app.config['HOST'], port=app.config['PORT'])

@app.route('/filter', methods=['POST'])
def filter_data():
    global data_filter
    data_filter = request.data.decode('utf-8')
    return "OK"