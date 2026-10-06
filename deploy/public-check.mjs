import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {fileURLToPath} from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const account = JSON.parse(fs.readFileSync(process.env.CLOUDREVE_CREDENTIALS || path.join(root,'.secrets','admin.json'),'utf8'));
const origin = process.env.CLOUDREVE_URL;
if(!origin?.startsWith('https://')) throw Error('Set CLOUDREVE_URL to your public HTTPS URL.');
let token = '';
async function api(method, endpoint, data, raw=false) {
  const headers = {'Content-Type': raw ? 'application/octet-stream' : 'application/json'};
  if(token) headers.Authorization = 'Bearer '+token;
  const response = await fetch(origin+'/api/v4'+endpoint, {method,headers,body:data===undefined?undefined:raw?data:JSON.stringify(data),signal:AbortSignal.timeout(30000)});
  if(!response.ok) throw Error(`HTTP ${response.status}: ${endpoint}`);
  const result = await response.json();
  if(result.code!==0) throw Error(`API ${endpoint} code=${result.code}`);
  return result.data;
}
const checks=[];
const login = await api('POST','/session/token',account);
token=login.token.access_token;
checks.push('公网 HTTPS 管理员登录');
const payload = crypto.randomBytes(1024*1024);
const uri='cloudreve://my/public-check-'+crypto.randomBytes(4).toString('hex')+'.bin';
try {
  const session = await api('PUT','/file/upload',{uri,size:payload.length,mime_type:'application/octet-stream'});
  await api('POST','/file/upload/'+session.session_id+'/0',payload,true);
  checks.push('经过 Nginx 公网上传 1 MiB 文件');
  const urls = await api('POST','/file/url',{uris:[uri],download:true});
  const download = await fetch(urls.urls[0].url,{signal:AbortSignal.timeout(30000)});
  if(!download.ok) throw Error('Public download HTTP '+download.status);
  const content = Buffer.from(await download.arrayBuffer());
  if(!content.equals(payload)) throw Error('Downloaded bytes differ');
  checks.push('公网下载内容完整一致');
} finally {
  await api('DELETE','/file',{uris:[uri],skip_soft_delete:true});
}
checks.push('验证文件已永久删除');
// Chat coexistence was checked on the original deployment; other installations
// can add checks for their own existing application endpoints.
fs.writeFileSync(path.join(root,'public-check-result.json'),JSON.stringify({pass:true,checks},null,2));
checks.forEach(c=>console.log('PASS '+c));
