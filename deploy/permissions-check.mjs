import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {fileURLToPath} from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const origin=process.env.CLOUDREVE_URL;
if(!origin?.startsWith('https://'))throw Error('Set CLOUDREVE_URL to the HTTPS site URL');
const account=JSON.parse(fs.readFileSync(process.env.CLOUDREVE_CREDENTIALS||path.join(root,'.secrets','admin.json'),'utf8'));
let token='';const checks=[],created=[],denials=[];
async function api(method,endpoint,data,raw=false,denied=false){
 const headers={'Content-Type':raw?'text/plain;charset=utf-8':'application/json'};if(token)headers.Authorization='Bearer '+token;
 const response=await fetch(origin+'/api/v4'+endpoint,{method,headers,body:data===undefined?undefined:raw?data:JSON.stringify(data),signal:AbortSignal.timeout(30000)});
 const result=await response.json();
 if(denied){
  const expected=[401,403,40076,40082].includes(result.code)||(result.code===40081&&/"code":(401|403|40082)[,}]/.test(JSON.stringify(result.aggregated_error)));
  if(!expected)throw Error('Expected permission/version rejection: '+endpoint+' code='+result.code);
  denials.push({endpoint,status:response.status,code:result.code});return result;
 }
 if(!response.ok||result.code!==0)throw Error(endpoint+' failed, HTTP='+response.status+' code='+result.code+' msg='+result.msg);
 return result.data;
}
const login=await api('POST','/session/token',account),admin=login.token.access_token;token=admin;
if(process.argv.includes('--apply')){
 await api('PATCH','/admin/settings',{settings:{register_enabled:'1',reg_captcha:'1',default_group:'2'}});
 for(const id of [1,2,3]){
  const group=await api('GET','/admin/group/'+id),permissions=Buffer.from(group.permissions,'base64');
  if(id===1)permissions[0]|=1;else permissions[0]&=~1;
  if(id===3)permissions[0]&=~(1<<7);
  group.permissions=permissions.toString('base64');await api('PUT','/admin/group/'+id,{group});
 }
 checks.push('注册默认分配普通用户组，管理员标记仅授予管理员，关闭匿名分享下载');
}
try{
 for(const label of ['A','B']){
  token=admin;const email='permission-'+crypto.randomBytes(6).toString('hex')+'@example.com',password=crypto.randomBytes(18).toString('hex');
  const user=await api('PUT','/admin/user',{user:{email,nick:'权限验证'+label,status:'active',group_users:2,settings:{}},password});
  created.push({id:user.id,email,password});
  token='';const session=await api('POST','/session/token',{email,password});Object.assign(created.at(-1),{token:session.token.access_token,hash:session.user.id});
 }
 const [a,b]=created;const name='permission-'+crypto.randomBytes(4).toString('hex')+'.txt';const uri='cloudreve://my/'+name;
 token=a.token;
 const content='用户 A 上传的原始内容',session=await api('PUT','/file/upload',{uri,size:Buffer.byteLength(content),mime_type:'text/plain'});
 await api('POST','/file/upload/'+session.session_id+'/0',content,true);
 await api('PUT','/file/content?uri='+encodeURIComponent(uri),'用户 A 修改自己的内容',true);checks.push('普通用户可上传并编辑自己的文件');
 token=b.token;const foreign='cloudreve://'+a.hash+'@my/'+name;
 await api('GET','/file?uri='+encodeURIComponent('cloudreve://'+a.hash+'@my/'),undefined,false,true);
 await api('PUT','/file/content?uri='+encodeURIComponent(foreign),'用户 B 尝试修改',true,true);
 await api('POST','/file/rename',{uri:foreign,new_name:'not-allowed.txt'},false,true);
 await api('DELETE','/file',{uris:[foreign],skip_soft_delete:true},false,true);checks.push('另一普通用户无法列出、编辑、改名或删除他人文件');
 await api('POST','/admin/file',{page:1,page_size:10},false,true);checks.push('普通用户无法访问后台全空间管理');
 token='';await api('PUT','/file/upload',{uri:'cloudreve://my/anonymous.txt',size:1},false,true);checks.push('未登录访客无法上传');
 token=admin;const result=await api('POST','/admin/file',{page:1,page_size:50,conditions:{file_user:String(a.id)}});
 const file=result.files.find(f=>f.name===name);if(!file)throw Error('Administrator cannot see user file');
 token=b.token;await api('PUT','/admin/file/'+file.id+'/content','普通用户后台越权尝试',true,true);checks.push('管理员内容编辑接口拒绝普通用户');
 token=admin;const original=await api('GET','/admin/file/'+file.id);if(!original.content_version)throw Error('Content version missing');
 const changed='管理员修改整个空间的文件内容';await api('PUT','/admin/file/'+file.id+'/content?previous='+encodeURIComponent(original.content_version),changed,true);
 const url=await api('GET','/admin/file/url/'+file.id),response=await fetch(url);if(await response.text()!==changed)throw Error('Admin content edit not persisted');checks.push('管理员可编辑其他用户的文件内容，下载内容一致');
 await api('PUT','/admin/file/'+file.id+'/content?previous='+encodeURIComponent(original.content_version),'过期编辑不得覆盖',true,true);checks.push('过期版本的并发编辑被拒绝');
 const owner=await api('GET','/admin/user/'+a.id);await api('PUT','/admin/user/'+a.id,{user:{...owner,status:'manual_banned'},password:''});
 await api('PUT','/admin/file/'+file.id+'/content','管理员可维护停用账号的文件',true);checks.push('管理员可编辑停用账号的文件');
 const regular=await api('GET','/admin/group/2');if(Buffer.from(regular.permissions,'base64')[0]&1)throw Error('Regular group unexpectedly elevated');checks.push('管理员代编辑未改变普通用户组权限');
 const full=await api('GET','/admin/file/'+file.id);await api('PUT','/admin/file/'+file.id,{file:{...full,name:'admin-renamed.txt'}});checks.push('管理员可更改其他用户的文件名');
 await api('POST','/admin/file/batch/delete',{ids:[file.id]});checks.push('管理员可删除其他用户的文件');
}finally{
 token=admin;for(const user of created)await api('POST','/admin/user/batch/delete',{ids:[user.id]});
}
checks.push('临时验证账号与文件已清理');
fs.writeFileSync(path.join(root,'permissions-check-result.json'),JSON.stringify({pass:true,checks,denials},null,2));checks.forEach(c=>console.log('PASS '+c));
