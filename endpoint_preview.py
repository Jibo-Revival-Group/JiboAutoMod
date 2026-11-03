#!/usr/bin/env python3
"""Preview retained Jetstream API/Hub configuration, offline and without apply."""
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import importlib.util
import ipaddress
import json
import math
from pathlib import Path
import re
from urllib.parse import urlsplit


def sibling(name):
    spec=importlib.util.spec_from_file_location(name,Path(__file__).with_name(name+'.py'))
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module


B=sibling('capture_bundle')
P=B.P
FIELDS=('entrypoint_hostname','entrypoint_port','hub_hostname','hub_port','hub_secure')
LAN4=tuple(ipaddress.ip_network(value) for value in ('10.0.0.0/8','172.16.0.0/12','192.168.0.0/16','169.254.0.0/16'))
LAN6=ipaddress.ip_network('fc00::/7')


def require(value):
    if not value: raise ValueError('endpoint_preview_refused')


def sha(raw): return hashlib.sha256(raw).hexdigest()


def bounded_tree(value,depth=0,budget=None):
    if budget is None: budget=[2048]
    budget[0]-=1; require(budget[0]>=0 and depth<=16)
    if type(value) is dict:
        require(len(value)<=512 and all(type(k) is str and len(k)<=128 for k in value))
        for item in value.values(): bounded_tree(item,depth+1,budget)
    elif type(value) is list:
        require(len(value)<=512)
        for item in value: bounded_tree(item,depth+1,budget)
    elif type(value) is str: require(len(value)<=4096)
    elif type(value) is int: require(-(1<<63)<=value<(1<<63))
    elif type(value) is float: require(math.isfinite(value))
    else: require(value is None or type(value) is bool)


def read_json(path,pin):
    require(type(pin) is str and P.HASH.fullmatch(pin))
    raw=B.read(path,P.LIMIT); require(sha(raw)==pin)
    def integer(text):
        require(len(text)<=20); return int(text)
    value=json.loads(raw.decode('utf-8'),object_pairs_hook=P.no_duplicates,parse_int=integer,
                     parse_constant=lambda _:require(False))
    bounded_tree(value); return value,raw


def endpoint(origin,selection):
    P.target(dict(selection,apiOrigin=origin))
    parsed=urlsplit(origin); hostname=parsed.hostname.lower()
    try: address=ipaddress.ip_address(hostname)
    except ValueError:
        require(len(hostname)<=253 and all(re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?',label) for label in hostname.split('.')))
        require('.' in hostname); local=hostname.endswith('.local')
    else:
        hostname=address.compressed
        local=any(address in net for net in LAN4) if address.version==4 else address in LAN6
    if parsed.scheme=='http': require(selection['mode']=='isolated' and local)
    return dict(hostname=hostname,port=parsed.port or (443 if parsed.scheme=='https' else 80),secure=parsed.scheme=='https')


def routing_entry(value):
    require(type(value) is dict and set(value).issubset(FIELDS))
    for key,item in value.items():
        if key.endswith('_hostname'): require(type(item) is str and 0<len(item)<=253 and all(33<=ord(c)<=126 for c in item))
        elif key.endswith('_port'): require(type(item) is int and 1<=item<=65535)
        else: require(type(item) is bool)


def project(config,region,api,hub):
    require(type(config) is dict and 'regions' not in config and 'region-settings' not in config)
    client=config.get('HubClient'); require(type(client) is dict)
    settings=client.get('region-settings'); require(type(settings) is dict and region in settings)
    routing_entry(settings[region])
    if 'override' in client: routing_entry(client['override'])
    projected=copy.deepcopy(config); next_client=projected['HubClient']
    values=dict(entrypoint_hostname=api['hostname'],entrypoint_port=api['port'],hub_hostname=hub['hostname'],hub_port=hub['port'],hub_secure=hub['secure'])
    changes=[]
    for name,path,before in [('region','/HubClient/region-settings/'+region,settings[region]),('override','/HubClient/override',client.get('override',{}))]:
        updated=next_client['region-settings'][region] if name=='region' else next_client.setdefault('override',{})
        for key,value in values.items():
            if key not in before or type(before[key]) is not type(value) or before[key]!=value:
                # Only known routing values enter the review; unrelated settings stay private in payload files.
                changes.append(dict(path=path+'/'+key,operation='replace' if key in before else 'add',
                                    beforePresent=key in before,before=before.get(key),after=value))
            updated[key]=value
    return projected,changes


def trust_requirement(name,value):
    return dict(endpoint=name,hostname=value['hostname'],port=value['port'],tlsRequired=value['secure'],
                certificateChainValidationRequired=value['secure'],hostnameValidationRequired=value['secure'],
                trustStoreCompatibilityVerified=False,certificateChainVerified=False,certificateChangesPlanned=False,
                disableCertificateValidationPermitted=False)


def preview(manifest_path,manifest_pin,target_path,target_pin,jetstream_path,output):
    manifest,_=read_json(manifest_path,manifest_pin); selection,_=read_json(target_path,target_pin)
    P.exact(manifest,('schema','targetSha256','jetstream','credentialsRegion','hubOrigin','allowIsolatedHttp','certificatePolicy'),'endpoint_manifest_fields')
    require(manifest['schema']=='openjibo.endpoint-preview-input.v1' and manifest['targetSha256']==target_pin)
    P.target(selection)
    require(type(manifest['credentialsRegion']) is str and re.fullmatch('[a-z][a-z0-9-]{0,31}',manifest['credentialsRegion']))
    require(type(manifest['allowIsolatedHttp']) is bool and manifest['certificatePolicy']=='preserve-existing')
    P.exact(manifest['jetstream'],('sha256','sizeBytes'),'jetstream_fields')
    require(type(manifest['jetstream']['sizeBytes']) is int and 0<manifest['jetstream']['sizeBytes']<=P.LIMIT)
    config,raw=read_json(jetstream_path,manifest['jetstream']['sha256'])
    require(len(raw)==manifest['jetstream']['sizeBytes'])
    api=endpoint(selection['apiOrigin'],selection); hub=endpoint(manifest['hubOrigin'],selection)
    http=not api['secure'] or not hub['secure']; require(manifest['allowIsolatedHttp'] is http)
    projected,changes=project(config,manifest['credentialsRegion'],api,hub)
    after=P.canonical(projected)+b'\n' if changes else raw
    require(len(after)<=P.LIMIT)
    blockers=['physical-device-and-installed-release-association-unverified','effective-runtime-endpoint-and-protocol-precedence-unverified',
              'native-notification-token-and-ssm-routing-not-planned','dns-and-robot-network-reachability-unverified',
              'filesystem-allocation-and-sector-change-plan-not-produced','device-specific-recovery-and-rollback-unverified',
              'complete-conversion-review-and-bounded-apply-readback-required']
    if api['secure'] or hub['secure']: blockers.append('robot-tls-chain-hostname-and-trust-store-acceptance-unverified')
    if http: blockers.append('isolated-lan-http-is-explicitly-acknowledged-but-network-is-unverified')
    if selection['mode']!='isolated': blockers.append('provider-ownership-enrollment-and-issued-credentials-unverified')
    result=dict(schema='openjibo.endpoint-file-preview.v1',checkedAtUtc=datetime.now(timezone.utc).isoformat(),
                manifestSha256=manifest_pin,manifestCanonicalSha256=P.digest(manifest),targetSha256=target_pin,targetCanonicalSha256=P.digest(selection),
                target=selection,credentialsRegion=manifest['credentialsRegion'],regionOrigin='operator-supplied-not-credential-file-verified',
                file='/usr/local/etc/jibo-jetstream-service.json',beforeSha256=sha(raw),afterSha256=sha(after),beforeSizeBytes=len(raw),afterSizeBytes=len(after),
                beforeFile='jetstream.before.json' if changes else None,afterFile='jetstream.after.json' if changes else None,
                changeRequired=bool(changes),semanticChanges=changes,projectedEndpoints=dict(api=api,hub=hub),
                unrelatedJsonValuesPreserved=True,formattingMayChange=bool(changes),previewComplete=True,completeConversionPlan=False,
                certificatePolicy='preserve-existing',trustRequirements=[trust_requirement('api',api),trust_requirement('hub',hub)],
                credentialsChanged=False,certificatesChanged=False,privateKeyFilesRead=False,certificateFilesRead=False,nativeLibraryChangesPlanned=False,
                notificationOrSsmChangesPlanned=False,dnsChangesPlanned=False,sectorChangesPlanned=False,
                executionSupported=False,readyForApply=False,deviceWritesPerformed=False,networkRequestsPerformed=False,
                robotCompatibilityVerified=False,providerOwnershipVerified=False,inputTrust='operator-pinned-not-provenance-or-device-authenticated',
                requiredBeforeApply=blockers,codeSha256=dict(preview=sha(Path(__file__).read_bytes()),preparation=sha(Path(P.__file__).read_bytes()),
                    byteReader=sha(Path(B.__file__).read_bytes()),pathChecker=sha(Path(B.A.R.__file__).read_bytes())))
    output=B.new_directory(output)
    if changes:
        B.write(output/'jetstream.before.json',raw); B.write(output/'jetstream.after.json',after)
    P.export(result,output/'preview.json'); return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('manifest','target','jetstream','output'): parser.add_argument('--'+name,required=True,type=Path)
    for name in ('manifest-sha256','target-sha256'): parser.add_argument('--'+name,required=True)
    args=parser.parse_args()
    try: result=preview(args.manifest,args.manifest_sha256,args.target,args.target_sha256,args.jetstream,args.output)
    except (ValueError,OSError,UnicodeError,KeyError,TypeError,B.A.CaptureFailure,RecursionError):
        parser.exit(2,'Endpoint preview refused; check pins, explicit target/routes, supported config and new output.\n')
    print(json.dumps(dict(previewComplete=True,changeRequired=result['changeRequired'],previewSha256=P.digest(result),readyForApply=False)))


if __name__=='__main__': main()
