#################################################################
#################################################################
############### Notebook Generator Website ######################
#################################################################
#################################################################
##### Author: Denis Torre
##### Affiliation: Ma'ayan Laboratory,
##### Icahn School of Medicine at Mount Sinai

#######################################################
#######################################################
########## 1. App Configuration
#######################################################
#######################################################

#############################################
########## 1. Load libraries
#############################################
##### 1. Flask modules #####
from flask import Flask, request, render_template, Response, redirect, url_for
from flask_sqlalchemy import SQLAlchemy

##### 2. Python modules #####
import sys, os, json, requests
import pandas as pd
import pymysql
pymysql.install_as_MySQLdb()

##### 3. Custom modules #####

#############################################
########## 2. App Setup
#############################################
##### 1. Flask App #####
# General
entry_point = '/notebook-generator-website'
app = Flask(__name__, static_url_path=os.path.join(entry_point, 'static'))

# Database
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ['SQLALCHEMY_DATABASE_URI']
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
engine = db.engine

#######################################################
#######################################################
########## 2. Server
#######################################################
#######################################################

#############################################
########## 1. Home
#############################################

@app.route(entry_point)
def index():
	return render_template('index.html')

#############################################
########## 2. Analyze
#############################################

@app.route(entry_point+'/analyze')
def analyze():
	return render_template('analyze.html')

#############################################
########## 3. Search Data
#############################################

@app.route(entry_point+'/analyze/search')
def search_data():
	d = pd.read_sql_query('SELECT DISTINCT gpl, gse FROM series se LEFT JOIN sample sa ON se.id=sa.series_fk LEFT JOIN platform p ON p.id=sa.platform_fk', engine).head()
	return render_template('search_data.html', d=d)

#############################################
########## 4. Upload Data
#############################################

@app.route(entry_point+'/analyze/upload')
def upload_data():
	return render_template('upload_data.html')

#############################################
########## 5. Add Tools
#############################################

@app.route(entry_point+'/analyze/tools', methods=['GET', 'POST'])
def add_tools():
	t = pd.read_sql_table('tool', engine).head(7)
	d = {'gse': request.form.get('gse-gpl').split('-')[0], 'gpl': request.form.get('gse-gpl').split('-')[1]}
	return render_template('add_tools.html', d=d, t=t)

#############################################
########## 6. Configure Analysis
#############################################

@app.route(entry_point+'/analyze/configure', methods=['GET', 'POST'])
def configure_analysis():
	f=request.form
	signature_tools = pd.read_sql_query('SELECT tool_string FROM tool WHERE requires_signature = TRUE', engine)['tool_string'].values
	requires_signature = any([x in signature_tools for x in [x for x in f.lists()][-1][-1]])
	if requires_signature:
		j = pd.read_sql_query('SELECT CONCAT(gsm, "---", sample_title) AS sample_info, variable, value FROM sample s LEFT JOIN series g ON g.id=s.series_fk LEFT JOIN sample_metadata sm ON s.id=sm.sample_fk WHERE gse = "{}"'.format(f.get('gse')), engine).pivot(index='sample_info', columns='variable', values='value')
		j = pd.concat([pd.DataFrame({'accession': [x.split('---')[0] for x in j.index], 'sample': [x.split('---')[1] for x in j.index]}, index=j.index), j], axis=1).reset_index(drop=True).fillna('')
		j = j[[col for col, colData in j.iteritems() if len(colData.unique()) > 1]]
		return render_template('configure_signature.html', f=f, j=j)
	else:
		tools = '("'+'","'.join([value for value, key in zip(f.listvalues(), f.keys()) if key == 'tool'][0])+'")'
		p = pd.read_sql_query('SELECT tool_name, tool_string, parameter_name, parameter_description, parameter_string, value, `default` FROM parameter p LEFT JOIN tool t ON t.id=p.tool_fk LEFT JOIN parameter_value pv ON p.id=pv.parameter_fk WHERE t.tool_string IN {}'.format(tools), engine).set_index(['tool_name'])#.set_index(['tool_name', 'parameter_name', 'parameter_description', 'parameter_string'])
		d = {}
		for index, rowData in p.iterrows():
			if index not in d.keys():
				d[index] = {'parameters': {}, 'tool_string': rowData['tool_string']}
			if rowData['parameter_string'] not in d[index]['parameters'].keys():
				d[index]['parameters'][rowData['parameter_string']] = {x: rowData[x] for x in ['parameter_description', 'parameter_name']}
				d[index]['parameters'][rowData['parameter_string']]['values'] = []
			d[index]['parameters'][rowData['parameter_string']]['values'].append({'value': rowData['value'], 'default': rowData['default']})
		print(tools)
		return render_template('review_analysis.html', f=f, d=d, p=p)

#############################################
########## 7. Generate Notebook
#############################################

@app.route(entry_point+'/analyze/generate', methods=['GET', 'POST'])
def generate_notebook():
	d = {key:value if len(value) > 1 else value[0] for key, value in request.form.lists()}
	p = {x:{} for x in d['tool']}
	g = {x:[] for x in ['a', 'b']}
	for key, value in d.items():
		if '-' in key:
			if 'GSM' in key:
				g[value].append(key.split('-')[0])
			else:
				tool_string, parameter_string = key.split('-')
				p[tool_string][parameter_string] = value

	c = {
		'notebook': {'title': d['notebook_title'], 'live': 'False', 'version': 'v0.3'},
		'tools': [{'tool_string': x, 'parameters': p.get(x, {})} for x in d['tool']],
		'data': {'source': 'archs4', 'parameters': {'gse': d['gse'], 'platform': d['gpl']}},
		'signature': {"method": "limma",
			"A": {"name": d.get('group_a_label'), "samples": g['a']},
			"B": {"name": d.get('group_b_label'), "samples": g['b']}}
	}
	r = requests.post('http://amp.pharm.mssm.edu/notebook-generator-server/api/generate', data=json.dumps(c), headers={'content-type':'application/json'})
	return r.text

#############################################
########## 8. Search Datasets
#############################################

@app.route(entry_point+'/api/search_datasets', methods=['POST'])
def search_datasets():
	d = pd.read_sql_query('SELECT gse, gpl, title, summary, COUNT(*) AS nr_samples FROM series se LEFT JOIN sample sa ON se.id=sa.series_fk LEFT JOIN platform p ON p.id=sa.platform_fk WHERE title LIKE "%%{search}%%" OR summary LIKE "%%{search}%%" GROUP BY gse LIMIT 50'.format(**request.json), engine)
	return json.dumps(d.to_dict(orient='records'))

#######################################################
#######################################################
########## Run App
#######################################################
#######################################################

#############################################
########## 1. Run
#############################################
if __name__ == "__main__":
	app.run(debug=True, host='0.0.0.0')