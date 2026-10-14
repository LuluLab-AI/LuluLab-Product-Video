#!/usr/bin/env python3
"""Client-only wrapper for SalesVideoPromptV2 via the upstream LuluLab CLI."""
import argparse,json,subprocess,os,sys,time,pathlib,hashlib
from language_context import resolve
from model_catalog import model_id_for, validate_durations, DEFAULT_MODEL
from prompt_validator import validate_result
import video_cli
WF='SalesVideoPromptV2'
def call(args):
 p=subprocess.run(args,capture_output=True,text=True,timeout=80)
 if p.returncode: raise RuntimeError('CLI failed: '+(p.stderr or p.stdout)[-600:])
 try:return json.loads(p.stdout)
 except:raise RuntimeError('CLI output was not valid JSON')
def unwrap(obj, model="seedance-2-mini", target=15):
 # CLI fetch may yield output directly or workflow task envelope
 o=obj.get('output',obj)
 if isinstance(o,dict) and 'output' in o and not 'videoPrompts' in o: o=o['output']
 if isinstance(o,str): o=json.loads(o)
 if isinstance(o,dict) and o.get('success') is False:raise ValueError(o.get('message','workflow failed'))
 if not isinstance(o,dict):raise ValueError('missing workflow output')
 for k in ('videoPrompts','creatorPrompts'):
  if not isinstance(o.get(k),dict):raise ValueError('missing '+k)
 seg=o['videoPrompts'].get('segments')
 if not isinstance(seg,list) or not seg:raise ValueError('no segments')
 for i,s in enumerate(seg,1):
  if s.get('segmentId')!=i or not isinstance(s.get('prompt'),str) or not s['prompt'].strip():raise ValueError('invalid segment')
  if not isinstance(s.get('duration'),int):raise ValueError('invalid model segment duration')
 validate_durations(model,[s['duration'] for s in seg],target)
 validate_result({'videoPrompts':o['videoPrompts'],'creatorPrompts':o['creatorPrompts']},
                 video_model=model,target_duration=target)
 return {'videoPrompts':o['videoPrompts'],'creatorPrompts':o['creatorPrompts']}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--input');ap.add_argument('--output',required=True);ap.add_argument('--resume-task-id');ap.add_argument('--cli',default=str(pathlib.Path(__file__).parent/'lululab_cli.mjs'));ap.add_argument('--interval',type=int,default=5);ap.add_argument('--max-polls',type=int,default=120);a=ap.parse_args()
 cli=['node',a.cli];out=pathlib.Path(a.output);out.parent.mkdir(parents=True,exist_ok=True)
 state=out.with_suffix('.task.json')
 payload={}
 if a.input: payload=json.load(open(a.input,encoding='utf-8'))
 if not a.resume_task_id and a.input: payload=resolve(payload)
 config=payload.get('userConfig') or {}
 model=model_id_for(config.get('videoModel',DEFAULT_MODEL));target=int(config.get('duration',15))
 if not 4 <= target <= 60: raise ValueError('Target duration must be 4–60 seconds')
 if a.resume_task_id:
  task_id=a.resume_task_id
  if state.exists():
   saved=json.loads(state.read_text(encoding='utf-8'))
   if saved.get('taskId') and str(saved['taskId']) != str(task_id): raise ValueError('Resume task ID does not match persisted state')
   model=saved.get('model',model);target=int(saved.get('target',target))
   if a.input and saved.get('languages'):
    incoming=resolve(payload)['userConfig']
    if any(incoming.get(k)!=saved['languages'].get(k) for k in ('interactionLanguage','promptLanguage','mediaLanguage')):raise ValueError('Language configuration differs from submitted task; resume with original languages')
 else:
  if not a.input:ap.error('--input is required for submit')
  expected={'productBrief','userConfig','creativeRequirement','creatorBrief'}
  if set(payload) != expected: raise ValueError('Prompt request must contain exactly four top-level fields')
  if payload['userConfig'].get('videoStyle','ugcProductDemo') not in ('ugcProductDemo','storyDrivenAd'):
   raise ValueError('Unsupported videoStyle')
  if state.exists():raise RuntimeError(f'Previous task file exists: {state}; resume rather than resubmit')
  payload['userConfig']['videoModel']=model
  if video_cli.get_lululab_credit_balance() <= 0:
   raise video_cli.CreditsInsufficient(video_cli.CREDITS_MESSAGE)
  languages={k:payload['userConfig'][k] for k in ('interactionLanguage','promptLanguage','mediaLanguage')}
  task_context={'workflowId':WF,'model':model,'target':target,'languages':languages}
  state.write_text(json.dumps({'state':'submit_started_uncertain',**task_context},ensure_ascii=False))
  try:result=call(cli+['task','submit','--workflow-id',WF,'--input',json.dumps(payload,ensure_ascii=False)])
  except Exception:
   raise RuntimeError(f'Uncertain paid submission, inspect {state}; do not automatically retry')
  task_id=result.get('id') or result.get('taskId') or result.get('data',{}).get('id')
  if not task_id:raise RuntimeError('No task ID returned; do not resubmit')
  state.write_text(json.dumps({'state':'submitted','taskId':task_id,**task_context},ensure_ascii=False))
 for _ in range(a.max_polls):
  task=call(cli+['task','fetch','--id',str(task_id)])
  obj=task.get('data',task);status=str(obj.get('status','')).lower()
  if status in ('succeeded','success','completed'):
   result=unwrap(obj,model,target);out.write_text(json.dumps(result,ensure_ascii=False,indent=2));state.write_text(json.dumps({'state':'succeeded','taskId':task_id,**({'model':model,'target':target,'languages':saved.get('languages')} if a.resume_task_id and state.exists() else task_context)},ensure_ascii=False));print(json.dumps({'taskId':task_id,'output':str(out)},ensure_ascii=False));return
  if status in ('failed','cancelled','canceled'):
   state.write_text(json.dumps({'state':status,'taskId':task_id,'model':model,'target':target, 'languages':(json.loads(state.read_text()).get('languages'))},ensure_ascii=False));raise RuntimeError(f'Workflow {task_id} failed, not resubmitting')
  time.sleep(a.interval)
 state.write_text(json.dumps({'state':'poll_timeout','taskId':task_id,'model':model,'target':target,'languages':json.loads(state.read_text()).get('languages')},ensure_ascii=False));raise RuntimeError(f'Polling budget exhausted, resume same task ID {task_id}')
if __name__=='__main__':main()
