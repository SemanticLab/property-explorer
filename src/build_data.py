import requests
import json
from operator import *
from datetime import date


def chunks(lst, n):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

SPARQL_ENDPOINT = 'https://query.semlab.io/proxy/wdqs/bigdata/namespace/wdq/sparql'

labelLookup = {}

def getLabel(qid):
    global labelLookup

    if qid in labelLookup:
        return(labelLookup[qid])
    elif qid == 'Literal':
        return 'Literal'
    else:
        return(f"semlab:{qid}")

# get the labels for everything
sparql = """
    SELECT ?item ?itemLabel 
    WHERE 
    {
      ?item wdt:P1 ?type. 
      SERVICE wikibase:label { bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en". } # Helps get the label in your language, if not, then en language
    }
"""
headers = {
    'Accept': 'application/sparql-results+json',
}
params = {
    'query' : sparql
}
response = requests.get(
    SPARQL_ENDPOINT,
    params=params,
    headers=headers,
)
data = response.json()

for result in data['results']['bindings']:
    print(result)
    labelLookup[result['item']['value'].split('/')[-1]] = result['itemLabel']['value']
    print(result['item']['value'].split('/')[-1])




sparql = """
SELECT ?property ?propertyLabel ?exportAlias ?propertyDescription (GROUP_CONCAT(DISTINCT(?altLabel); separator = ", ") AS ?altLabel_list) (GROUP_CONCAT(DISTINCT(?equalProp); separator = ", ") AS ?equalProp_list) WHERE {
    ?property a wikibase:Property .
    OPTIONAL { ?property skos:altLabel ?altLabel . FILTER (lang(?altLabel) = "en") }
    OPTIONAL { ?property wdt:P41 ?equalProp .}
    OPTIONAL { ?property wdt:P204 ?exportAlias .}
    SERVICE wikibase:label { bd:serviceParam wikibase:language "en" .}
 }
GROUP BY ?property ?propertyLabel ?exportAlias ?propertyDescription
LIMIT 5000

"""
headers = {
    'Accept': 'application/sparql-results+json',
}
params = {
	'query' : sparql
}
response = requests.get(
    SPARQL_ENDPOINT,
    params=params,
    headers=headers,
)

properties = {
    
}
pids = []
data = response.json()
for result in data['results']['bindings']:

    pid = result['property']['value'].split("/")[-1]
    properties[pid] = {}

    properties[pid]['uri'] = result['property']['value']
    properties[pid]['label'] = result['propertyLabel']['value']
    if 'exportAlias' in result:
        properties[pid]['alias'] = result['exportAlias']['value']
        print(properties[pid]['alias'])
    else:
        print("no alias ", pid)
        properties[pid]['alias'] = pid

    if 'propertyDescription' in result:
        properties[pid]['description'] = result['propertyDescription']['value']
    
    if 'altLabel_list' in result:
        properties[pid]['altlabel'] = result['altLabel_list']['value']
    
    if 'equalProp_list' in result:
        properties[pid]['equivalent'] = result['equalProp_list']['value']

    pids.append(pid)

# sort the pids numericly
num_pids = []
for p in pids:
    num_pids.append(int(p[1:]))
pids = []
for num in sorted(num_pids):
    pids.append(f'P{num}')


# ask for the data types for each property
for c in chunks(pids,20):
    ps = "|".join(c)
    response = requests.get(f"https://base.semlab.io/w/api.php?action=wbgetentities&ids={ps}&format=json")
    data = response.json()
    for p in data['entities']:
        properties[p]['type'] = data['entities'][p]['datatype']



counter = 0
for p in pids:


    counter = counter + 1
    print(counter,'/',len(properties), f"({p})")
    if properties[p]['type'] == 'wikibase-item':

        sparql = f"""
            SELECT ?instanceOfSub ?instanceOfObj (GROUP_CONCAT(DISTINCT(?parojectSub); separator = ", ") AS ?parojectSub_list) (GROUP_CONCAT(DISTINCT(?parojectObj); separator = ", ") AS ?parojectObj_list) (COUNT(?instanceOfSub) AS ?instanceOfSub_count) (COUNT(?instanceOfObj) AS ?instanceOfObj_count)
            WHERE 
            {{
                ?item1 wdt:{p} ?item2.
                ?item1 wdt:P1 ?instanceOfSub .
                ?item2 wdt:P1 ?instanceOfObj .
            
                optional{{
                    ?item1 wdt:P11 ?parojectSub .
                }}
                optional{{
                    ?item2 wdt:P11 ?parojectObj .
                }}    
            }}
            GROUP BY ?instanceOfSub ?instanceOfObj

        """

    else:
        sparql = f"""
            SELECT ?instanceOfSub ?instanceOfObj (GROUP_CONCAT(DISTINCT(?parojectSub); separator = ", ") AS ?parojectSub_list) (COUNT(?instanceOfSub) AS ?instanceOfSub_count)
            WHERE 
            {{
                ?item1 wdt:{p} ?item2.
                ?item1 wdt:P1 ?instanceOfSub .
            
                optional{{
                    ?item1 wdt:P11 ?parojectSub .
                }}
            }}
            GROUP BY ?instanceOfSub ?instanceOfObj

        """
    print(sparql)

    headers = {
        'Accept': 'application/sparql-results+json',
    }
    params = {
        'query' : sparql
    }
    response = requests.get(
        SPARQL_ENDPOINT,
        params=params,
        headers=headers,
    )

    data = response.json()
    properties[p]['instanceOfStats'] = {} 
    properties[p]['projectsQids'] = {'all':[],'sub':[],'obj':[]}
    properties[p]['projects'] = []
    properties[p]['projectsSub'] = []
    properties[p]['projectsObj'] = []
    counter2=0
    for result in data['results']['bindings']:
        counter2=counter2+1
        print("\t",counter2, len(data['results']['bindings']))
        subType = result['instanceOfSub']['value'].split("/")[-1]
        if 'instanceOfObj' in result:
            objType = result['instanceOfObj']['value'].split("/")[-1]
        else:
            objType = 'Literal'


        if objType != 'Literal':

            # get an accurate count for it
            sparql = f"""
                SELECT ?subject ?subjectLabel ?object ?objectLabel 
                WHERE 
                {{
                  ?subject wdt:{p} ?object.
                  ?subject wdt:P1 wd:{subType}.
                  ?object wdt:P1 wd:{objType} .
                  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en". }} 
                }}
            """

        else:
            sparql = f"""
                SELECT ?subject ?subjectLabel ?object ?objectLabel 
                WHERE 
                {{
                  ?subject wdt:{p} ?object.
                  ?subject wdt:P1 wd:{subType}.
                  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en". }} 
                }}
            """



        params = {
            'query' : sparql
        }
        sub_response = requests.get(
            SPARQL_ENDPOINT,
            params=params,
            headers=headers,
        )
        sub_data = sub_response.json()            

        # print(">>>>>>>>>>>")
        # print(sparql)
        # print(int(result['instanceOfSub_count']['value']), len(sub_data['results']['bindings']))



        properties[p]['instanceOfStats'][f"{subType}-{objType}"] = len(sub_data['results']['bindings'])




        

    

        if 'parojectSub_list' in result:
            for project_uri in result['parojectSub_list']['value'].split(","):
                if project_uri.strip() == '':
                    continue


                project_qid = project_uri.split("/")[-1]

                if project_qid not in properties[p]['projectsQids']['all']:
                    if project_qid not in labelLookup:
                        print("No label found for project",project_qid)
                        continue
                    properties[p]['projectsQids']['all'].append(project_qid)
                    properties[p]['projects'].append({'qid':project_qid,'label':labelLookup[project_qid]})

                if project_qid not in properties[p]['projectsQids']['sub']:
                    if project_qid not in labelLookup:
                        print("No label found for project",project_qid)
                        continue                    
                    properties[p]['projectsQids']['sub'].append(project_qid)
                    properties[p]['projectsSub'].append({'qid':project_qid,'label':labelLookup[project_qid]})

        if 'parojectObj_list' in result:
            for project_uri in result['parojectObj_list']['value'].split(","):
                if project_uri.strip() == '':
                    continue                

                project_qid = project_uri.split("/")[-1]
                if project_qid not in properties[p]['projectsQids']['all']:
                    properties[p]['projectsQids']['all'].append(project_qid)
                    properties[p]['projects'].append({'qid':project_qid,'label':getLabel(project_qid)})
                
                if project_qid not in properties[p]['projectsQids']['obj']:
                    properties[p]['projectsQids']['obj'].append(project_qid)
                    properties[p]['projectsObj'].append({'qid':project_qid,'label':getLabel(project_qid)})


    total = 0
    for t in properties[p]['instanceOfStats']:
        total = total + properties[p]['instanceOfStats'][t]

    properties[p]['instanceOfStatsTotal'] = total
    properties[p]['instanceOfFacets'] = {} 
    for t in properties[p]['instanceOfStats']:

        stat = {
            'sub_qid': t.split('-')[0],
            'count': properties[p]['instanceOfStats'][t],
            'sub_label': getLabel(t.split('-')[0]),
            'percent': round(properties[p]['instanceOfStats'][t] / total * 100),
            'obj_qid': t.split('-')[1],
            'obj_label': getLabel(t.split('-')[1])
        }



        properties[p]['instanceOfFacets'][t] = stat



    properties[p]['subStats'] = {}
    properties[p]['objStats'] = {}
    properties[p]['subStatsTotal'] = 0
    properties[p]['objStatsTotal'] = 0

    for t in properties[p]['instanceOfFacets']:
        

        t = properties[p]['instanceOfFacets'][t]

        
        if t['sub_qid'] not in properties[p]['subStats']:
            properties[p]['subStats'][t['sub_qid']] = 0

        properties[p]['subStats'][t['sub_qid']] = properties[p]['subStats'][t['sub_qid']] + t['count']
        properties[p]['subStatsTotal']=properties[p]['subStatsTotal']+ t['count']
        if t['obj_qid'] not in properties[p]['objStats']:
            properties[p]['objStats'][t['obj_qid']] = 0

        properties[p]['objStats'][t['obj_qid']] = properties[p]['objStats'][t['obj_qid']] + t['count']
        properties[p]['objStatsTotal']=properties[p]['objStatsTotal']+ t['count']

    for qid in properties[p]['objStats']:
        properties[p]['objStats'][qid] = { 'qid': qid, 'count':properties[p]['objStats'][qid], 'percent': round(properties[p]['objStats'][qid] / properties[p]['subStatsTotal'] * 100), 'label': getLabel(qid)  }


    for qid in properties[p]['subStats']:
        properties[p]['subStats'][qid] = { 'qid': qid, 'count':properties[p]['subStats'][qid], 'percent': round(properties[p]['subStats'][qid] / properties[p]['objStatsTotal'] * 100), 'label': getLabel(qid)  }




global_qid_count = {}

for p in properties:

    for qid in properties[p]['objStats']:
        if qid not in global_qid_count:
            global_qid_count[qid] = 0

        global_qid_count[qid] = global_qid_count[qid] + properties[p]['objStats'][qid]['count']

    for qid in properties[p]['subStats']:
        if qid not in global_qid_count:
            global_qid_count[qid] = 0

        global_qid_count[qid] = global_qid_count[qid] + properties[p]['subStats'][qid]['count']



colors_touse = [
  [255,  69,   0],
  [0,   0, 255],
[144, 238, 144],
[240, 128, 128],
[220,  20,  60],
 [72,  61, 139],
[128,   0, 128],
[240, 230, 140],
[176,  48,  96],
[154, 205,  50],
  [0,   0, 139],
[124, 252,   0],
[255,  20, 147],
[218, 112, 214],
[255,   0, 255],
[138,  43, 226],
  [0, 191, 255],
[244, 164,  96],
  [0, 255, 127],
 [34, 139,  34],
[143, 188, 143],
[255, 165,   0],
  [0, 139, 139],
[173, 216, 230],
  [0, 255, 255],
[128, 128, 128],
[255, 255,   0],
 [30, 144, 255],
[139,  69,  19],
[128, 128,   0],
[123, 104, 238]]


qids_colors = {}

qids_sorted = sorted(global_qid_count.items(), key=lambda x:x[1], reverse=True)
for pair in qids_sorted:
    if len(colors_touse) > 0:
        if pair[0] != 'Literal':
            qids_colors[pair[0]] = colors_touse.pop(0)
    # else:
        # qids_colors[pair[0]] = None




for p in properties:

    subStatsSorted = sorted(properties[p]['subStats'].items(),key=lambda x:getitem(x[1],'count'),reverse=True)

    first_group = subStatsSorted[0:6]
    rest_group = subStatsSorted[7:]

    current_precent = 0;
    gradient_entries = []
    grays = ['#E5E4E2','#D3D3D3','#C0C0C0','#A9A9A9','#899499','#B2BEB5', '#848884', '#71797E', '#818589', '#708090']
    for fg in first_group:
        gradient_color = "white"

        current_precent = current_precent + fg[1]['percent']


        if fg[0] in qids_colors:
            # gradient_color = f"rgb({qids_colors[fg[0]][0]},{qids_colors[fg[0]][1]},{qids_colors[fg[0]][2]}) 0 {360 * (current_precent/100)}%"
            gradient_color = f"rgb({qids_colors[fg[0]][0]},{qids_colors[fg[0]][1]},{qids_colors[fg[0]][2]}) 0 {current_precent}%"
        else:

            rando_gray = grays.pop(1)

            gradient_color = f"{rando_gray} 0 {current_precent}%"

        gradient_entries.append(gradient_color)
        
    if len(rest_group) > 0:
        # gradient_entries.append(f"gray 0 {360 * ((100-current_precent)/100)}%")
        gradient_entries.append(f"gray 0 {100-current_precent}%")
    else:
        

        pass


    gradient = f"conic-gradient({','.join(gradient_entries)})"

    properties[p]['subStatsGradient'] = gradient

for p in properties:

    objStatsSorted = sorted(properties[p]['objStats'].items(),key=lambda x:getitem(x[1],'count'),reverse=True)
    first_group = objStatsSorted[0:6]
    rest_group = objStatsSorted[7:]

    current_precent = 0;
    gradient_entries = []
    grays = ['#E5E4E2','#D3D3D3','#C0C0C0','#A9A9A9','#899499','#B2BEB5', '#848884', '#71797E', '#818589', '#708090']
    for fg in first_group:
        gradient_color = "white"
        current_precent = current_precent + fg[1]['percent']
        if fg[0] in qids_colors:
            # gradient_color = f"rgb({qids_colors[fg[0]][0]},{qids_colors[fg[0]][1]},{qids_colors[fg[0]][2]}) 0 {360 * (current_precent/100)}%"
            gradient_color = f"rgb({qids_colors[fg[0]][0]},{qids_colors[fg[0]][1]},{qids_colors[fg[0]][2]}) 0 {current_precent}%"
        else:
            rando_gray = grays.pop(1)
            gradient_color = f"{rando_gray} 0 {current_precent}%"

        gradient_entries.append(gradient_color)
        
    if len(rest_group) > 0:
        # gradient_entries.append(f"gray 0 {360 * ((100-current_precent)/100)}%")
        gradient_entries.append(f"gray 0 {100-current_precent}%")
    else:

        pass


    gradient = f"conic-gradient({','.join(gradient_entries)})"

    properties[p]['objStatsGradient'] = gradient




json.dump({"properties":properties, 'qids':global_qid_count, 'qids_colors':qids_colors, 'date': str(date.today())},open("../data/properties.json",'w'),indent=2 )


# print(properties)




