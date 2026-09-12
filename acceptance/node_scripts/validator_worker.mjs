import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url);
const argv=process.argv.slice(2);
if(argv.length!==2 || argv[0]!=='--request') throw Error('exact --request argument required');
const request=JSON.parse(fs.readFileSync(argv[1],'utf8'));
const policy=request.parameters.policy;
const validator=require(path.join(policy.package_root,'node_modules/gltf-validator/index.js'));
if(validator.version()!==policy.validator_version) throw Error('validator version mismatch');
const input=request.inputs.find(x=>x.id==='delivery.glb');
if(!input || input.bytes>policy.limits.max_glb_bytes) throw Error('bounded GLB input required');
const raw=fs.readFileSync(path.join(request.input_root,input.path));
const sha=data=>crypto.createHash('sha256').update(data).digest('hex');
if(raw.length!==input.bytes || sha(raw)!==input.sha256) throw Error('GLB input identity mismatch');
const external=[];
const report=await validator.validateBytes(new Uint8Array(raw),{
    format:'glb',uri:'delivery.glb',maxIssues:10000,writeTimestamp:false,
    externalResourceFunction:async uri=>{external.push(uri);throw Error('external resource forbidden');}
});
const data={'validator.report':report,'validator.resources':{
    schema_version:2,input_sha256:input.sha256,input_bytes:raw.length,
    external_requests:external,resources:report.info?.resources??[]
}};
const artifacts=[];
for(const output of request.outputs){
    if(!Object.hasOwn(data,output.id)) throw Error('unknown validator output');
    const bytes=Buffer.from(JSON.stringify(data[output.id])+'\n');
    if(bytes.length>output.max_bytes) throw Error('validator report exceeds file budget');
    const target=path.join(request.output_root,output.path);
    fs.mkdirSync(path.dirname(target),{recursive:true});fs.writeFileSync(target,bytes,{flag:'wx'});
    artifacts.push({id:output.id,path:output.path,bytes:bytes.length,sha256:sha(bytes)});
}
const result=Object.fromEntries(['schema_version','run_id','attempt','nonce','job_id','writer','contract_digest','source_digest'].map(k=>[k,request[k]]));
Object.assign(result,{checks:[],artifacts,observations:{node:process.version,validator:validator.version(),pid:String(process.pid)}});
fs.writeFileSync(path.join(request.output_root,'result.json'),JSON.stringify(result)+'\n',{flag:'wx'});
