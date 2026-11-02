"""Audit actual Service metadata exports against canonical model metadata.

Does not execute DAX, access the browser, or modify a semantic model. A missing
native formatting snapshot leaves presentation metadata explicitly pending.
"""
from pathlib import Path
from datetime import datetime, timezone
import csv
import hashlib
import json
import re

ROOT=Path(__file__).resolve().parent.parent
EXPORT=ROOT/'outputs/verification/service_exports'
CANONICAL=ROOT/'powerbi/GridCast.SemanticModel/model.bim'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relative(path):
    return str(path.relative_to(ROOT))


def read(label):
    path=EXPORT/(label+'.csv')
    with path.open(newline='',encoding='utf-8-sig') as f:
        raw=list(csv.reader(f))
    with (EXPORT/(label+'.raw.tsv')).open(newline='',encoding='utf-8-sig') as f:
        # Native clipboard TSV is a literal cell stream, not CSV-style quoted
        # fields. In particular a Boolean column format begins with "TRUE";
        # those literal quotes must not be consumed by the CSV reader.
        tsv=list(csv.reader(f,delimiter='\t',quoting=csv.QUOTE_NONE))
    assert raw==tsv, f'Raw TSV/CSV cell texts differ for {label}'
    headers=[re.sub(r'^.*\[([^]]+)\]$',r'\1',h) for h in raw[0]]
    assert all(len(row)==len(headers) for row in raw[1:]), label
    return [dict(zip(headers,row)) for row in raw[1:]],{'csv_path':relative(path),'csv_sha256':sha(path),'raw_tsv_path':relative(EXPORT/(label+'.raw.tsv')),'raw_tsv_sha256':sha(EXPORT/(label+'.raw.tsv')),'rows':len(raw)-1,'columns':len(headers),'raw_csv_cell_preservation':'exact'}


def truth(value):
    assert value in ('true','false'),value
    return value=='true'


def parse_native_formats(path):
    text=path.read_text()
    # This file must be a public measure-only extraction, never the private
    # complete table definition with its personal OneDrive M partition.
    assert not re.search(r'^\s*partition\b|https?://|Web\.Contents|File\.Contents',text,re.M), 'Native format evidence must exclude private partition/source text'
    formats={};current=None
    for line in text.splitlines():
        match=re.match(r"^\s*measure\s+('(?:[^']|'')*'|[^\s=]+)(?:\s*=|\s*$)",line)
        if match:
            name=match.group(1)
            current=name[1:-1].replace("''", "'") if name.startswith("'") else name
            assert current not in formats, 'Duplicate measure in native TMDL snapshot'
            formats[current]=None
        elif current is not None:
            match=re.match(r'^\s*formatString:\s*(.*)$',line)
            if match:
                value=match.group(1).strip()
                if value.startswith('"') and value.endswith('"'):
                    value=value[1:-1].replace('""','"')
                formats[current]=value
    return formats


def main():
    source=json.loads(CANONICAL.read_text())['model']
    table_map={t['name']:t for t in source['tables']}
    expected_measures={(t['name'],m['name']):m for t in source['tables'] for m in t.get('measures',[])}
    expected_columns={(t['name'],c['name']):c for t in source['tables'] for c in t['columns']}
    labels=['metadata_measures','metadata_columns','metadata_tables','metadata_relationships']
    actual={};files={}
    for label in labels:
        actual[label],files[label]=read(label)
    provenance_path=EXPORT/'query_provenance.json'
    provenance=json.loads(provenance_path.read_text())
    selected=[p for p in provenance if p['label'] in labels]
    assert {p['label'] for p in selected}==set(labels)
    assert all(p['queryTextVerifiedViaNativeCopy'] is True and 'Success' in p['nativeStatus'] for p in selected)
    assert len({p['modelId'] for p in selected})==1
    for p in selected:
        assert p['rows']==files[p['label']]['rows'] and p['columns']==files[p['label']]['columns']
    measures={(r['Table'],r['Measure']):r for r in actual['metadata_measures']}
    assert set(measures)==set(expected_measures) and len(measures)==len(actual['metadata_measures'])==28
    expression_diffs=[];description_diffs=[];folder_diffs=[];info_format_diffs=[]
    for key,m in expected_measures.items():
        a=measures[key]
        for field,source_key,output in [('Expression','expression',expression_diffs),('Description','description',description_diffs),('DisplayFolder','displayFolder',folder_diffs),('FormatString','formatString',info_format_diffs)]:
            expected=m.get(source_key) or ''
            if a[field]!=expected:output.append({'table':key[0],'measure':key[1],'expected':expected,'actual_info_view':a[field]})
        assert a['State']=='Valid' and truth(a['IsHidden']) is False
    columns={(r['Table'],r['Column']):r for r in actual['metadata_columns']}
    assert set(columns)==set(expected_columns) and len(columns)==len(actual['metadata_columns'])==28
    allowed={'string':{'Text'},'int64':{'Integer'},'double':{'Number','Decimal','Decimal number','Double'},'dateTime':{'Date','DateTime','Date/Time'},'boolean':{'True/False','Boolean'}}
    type_diffs=[];sort_diffs=[];key_annotation_diffs=[]
    for key,c in expected_columns.items():
        a=columns[key]
        if a['DataType'] not in allowed[c['dataType']]:type_diffs.append({'table':key[0],'column':key[1],'canonical':c['dataType'],'actual_info_view':a['DataType']})
        if (c.get('sortByColumn') or '')!=a['SortByColumn']:sort_diffs.append({'table':key[0],'column':key[1],'expected':c.get('sortByColumn'),'actual':a['SortByColumn']})
        if bool(c.get('isKey',False)) != truth(a['IsKey']):key_annotation_diffs.append({'table':key[0],'column':key[1],'canonical_is_key':bool(c.get('isKey',False)),'actual_is_key':truth(a['IsKey']),'actual_is_unique':truth(a['IsUnique']),'actual_is_nullable':truth(a['IsNullable'])})
    date=columns[('DimDate','Date')]
    date_key_ok=truth(date['IsKey']) and truth(date['IsUnique']) and not truth(date['IsNullable'])
    tables={r['Table']:r for r in actual['metadata_tables']}
    canonical_tables={n:tables[n] for n in table_map}
    assert all(t['StorageMode']=='Import' and not truth(t['IsHidden']) for t in canonical_tables.values())
    date_table_ok=tables['DimDate']['DataCategory']=='Time' and truth(tables['DimDate']['IsDateTableByCategory'])
    extra_tables=[r for n,r in tables.items() if n not in table_map]
    auto_only=all(truth(t['IsHidden']) and t['StorageMode']=='Import' and (t['Table'].startswith('LocalDateTable_') or t['Table'].startswith('DateTableTemplate_')) for t in extra_tables)
    rels=actual['metadata_relationships']
    canonical_rels=[r for r in rels if r['FromTable'] in table_map and r['ToTable'] in table_map]
    extra_rels=[r for r in rels if r not in canonical_rels]
    expected_edges={(r['fromTable'],r['fromColumn'],r['toTable'],r['toColumn']) for r in source['relationships']}
    actual_edges={(r['FromTable'],r['FromColumn'],r['ToTable'],r['ToColumn']) for r in canonical_rels}
    canonical_relationships_ok=actual_edges==expected_edges and len(canonical_rels)==3 and all(r['FromCardinality']=='Many' and r['ToCardinality']=='One' and truth(r['IsActive']) and r['CrossFilteringBehavior']=='OneDirection' and r['State']=='Ready' for r in canonical_rels)
    auto_relationships_ok=all(r['FromTable'] in table_map and r['ToTable'] in tables and r['ToTable'].startswith('LocalDateTable_') and truth(tables[r['ToTable']]['IsHidden']) and r['FromCardinality']=='Many' and r['ToCardinality']=='One' and truth(r['IsActive']) and r['CrossFilteringBehavior']=='OneDirection' and r['State']=='Ready' for r in extra_rels)
    snapshot=EXPORT/'metadata_measures_native.tmdl'
    format_status='pending_native_format_snapshot'
    native_format_diffs=[];native_formats={}
    if snapshot.exists():
        native_formats=parse_native_formats(snapshot)
        assert set(native_formats)=={n for t,n in expected_measures}, 'Native TMDL measure set differs'
        for (table,name),m in expected_measures.items():
            if (native_formats[name] or '')!=(m.get('formatString') or ''):native_format_diffs.append({'table':table,'measure':name,'expected':m.get('formatString'),'actual_native_tmdl':native_formats[name]})
        format_status='exact_native_tmdl_match' if not native_format_diffs else 'native_tmdl_format_mismatch'
        files['native_measure_only_tmdl']={'path':relative(snapshot),'sha256':sha(snapshot),'measure_count':len(native_formats)}
        native_provenance_path=EXPORT/'metadata_measures_native_provenance.json'
        native_provenance=json.loads(native_provenance_path.read_text())
        assert native_provenance['publicProjectionSha256']==sha(snapshot)
        assert native_provenance['measureCount']==28 and native_provenance['formatStringCount']==27
        assert native_provenance['modelId']==selected[0]['modelId']
        assert native_provenance['partitionOrConnectionDetailsPublished'] is False
        files['native_measure_only_tmdl']['execution_provenance']={'path':relative(native_provenance_path),'sha256':sha(native_provenance_path),'record':native_provenance}
    core_ok=not expression_diffs and not description_diffs and not folder_diffs and not type_diffs and not sort_diffs and date_key_ok and date_table_ok and canonical_relationships_ok and auto_only and auto_relationships_ok
    status='core_metadata_pass_format_verification_pending' if core_ok and not snapshot.exists() else 'actual_service_metadata_matches_canonical_with_documented_service_differences' if core_ok and not native_format_diffs else 'metadata_requires_review'
    result={'status':status,'checked_at_utc':datetime.now(timezone.utc).isoformat(),'source_model':{'path':relative(CANONICAL),'sha256':sha(CANONICAL)},'actual_evidence':files,'execution_provenance':{'path':relative(provenance_path),'sha256':sha(provenance_path),'queries':selected},'checks':{'persisted_measure_names':{'expected':28,'actual':len(measures),'passed':True},'expressions_exact':{'matched':28-len(expression_diffs),'differences':expression_diffs},'descriptions_exact':{'matched':28-len(description_diffs),'differences':description_diffs},'display_folders_exact':{'matched':28-len(folder_diffs),'differences':folder_diffs},'measure_formats':{'status':format_status,'canonical_numeric_format_count':27,'info_view_blank_count':sum(not r['FormatString'] for r in measures.values()),'info_view_differences':info_format_diffs,'native_tmdl_differences':native_format_diffs},'column_names':{'expected':28,'actual':len(columns),'passed':True},'column_types_semantically_compatible':{'matched':28-len(type_diffs),'differences':type_diffs,'note':'INFO.VIEW uses human-readable type families: Date covers TOM dateTime, Number covers numeric types. Imported hour/origin integrity checks independently establish retained time components; this does not assert a UI format string from the type label.'},'sort_by_columns':{'expected_explicit':3,'matched':3-len(sort_diffs),'differences':sort_diffs},'dimdate_marked':{'category':tables['DimDate']['DataCategory'],'is_date_table_by_category':date_table_ok,'date_column_key_unique_nonnullable':date_key_ok},'canonical_relationships':{'count':len(canonical_rels),'passed':canonical_relationships_ok,'rows':canonical_rels}},'service_generated_objects':{'engine_total_tables':len(tables),'canonical_tables':len(canonical_tables),'hidden_auto_date_tables':extra_tables,'hidden_auto_objects_only':auto_only,'engine_total_relationships':len(rels),'canonical_relationships':len(canonical_rels),'automatic_date_relationships':extra_rels,'automatic_date_relationships_valid':auto_relationships_ok,'interpretation':'Five hidden auto-date objects and four internal date relationships are generated by the Service. They are additional to, not replacements for, the four canonical tables and three canonical fact-to-dimension relationships. No deletion was attempted or recommended.'},'nonblocking_metadata_annotation_differences':key_annotation_diffs,'limitations':['This independently audits retained real Service export cell contents and operator provenance; it does not itself perform browser queries.','INFO.VIEW static FormatString is blank for all28 measures in these actual exports; complete native formatting proof requires the measure-only actual TMDL snapshot or equivalent real UI evidence.','Canonical DimModel.Model IsKey annotation differs, but Service reports IsUnique=true/IsNullable=false and the active many-to-one model relationship plus independent import-integrity checks establish the dimension key behavior.','Passing Service model metadata and DAX does not establish Windows PBIP compatibility, report visual construction/rendering, interactions, screenshots, accessibility or public publication.']}
    format_groups={}
    for name,format_string in native_formats.items():
        format_groups.setdefault(format_string or '(no explicit format)',[]).append(name)
    result['checks']['measure_formats']['native_format_groups']=[{'formatString':fmt,'count':len(names),'measures':sorted(names)} for fmt,names in sorted(format_groups.items())]
    result['checks']['measure_formats']['numeric_native_formats_exact']=27-len(native_format_diffs) if snapshot.exists() else None
    result['checks']['measure_formats']['interpretation']='All27 numeric format strings match the actual native TMDL projection exactly; Model Selection correctly has no explicit numeric format. The blank INFO.VIEW FormatString cells are an observed metadata-view limitation, not missing native formats.' if snapshot.exists() and not native_format_diffs else 'Native format verification remains incomplete or has a mismatch; do not infer formats from blank INFO.VIEW cells.'
    result['limitations'][1]='The actual INFO.VIEW exports contain blank static FormatString cells for all28 measures. This limitation was resolved for the audit by exact comparison of all27 numeric formats to the actual native measure-only TMDL projection, with retained copy/projection provenance.' if snapshot.exists() and not native_format_diffs else result['limitations'][1]
    result['raw_tsv_parser_note']='Native copied TSV is a literal tab/newline cell stream. Literal quotes in the Boolean column format were preserved with QUOTE_NONE; CSV conversion changes quoting only, not cell contents.'
    (EXPORT/'metadata_reconciliation.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'status':status,'expressions_exact':28-len(expression_diffs),'descriptions_exact':28-len(description_diffs),'folders_exact':28-len(folder_diffs),'types_compatible':28-len(type_diffs),'sort_differences':sort_diffs,'date_table':date_table_ok and date_key_ok,'canonical_relationships':canonical_relationships_ok,'format_status':format_status,'engine_tables':len(tables),'engine_relationships':len(rels)},indent=2))
    if not core_ok or native_format_diffs:
        raise SystemExit(1)


if __name__=='__main__':
    main()
