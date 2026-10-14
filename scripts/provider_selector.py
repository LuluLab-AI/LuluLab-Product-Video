#!/usr/bin/env python3
"""Select first installed provider before paid generation, pin choice per video.
Availability is conservative: installed executable != authenticated. Adapters must perform
provider-specific authentication and model-schema preflight before submission.
"""
import argparse,json,pathlib,shutil,subprocess,sys,os
ORDER=('lululab_cli','libtv_cli','xiaoyunque_cli','dreamina_cli')
COMMANDS={'libtv_cli':['libtv'],'xiaoyunque_cli':['xiaoyunque'],'dreamina_cli':['dreamina'],'lululab_cli':['node']}
def select(preflights,explicit=None):
 for provider in ([explicit] if explicit else ORDER):
  state=preflights.get(provider,{})
  if state.get('available') is True and state.get('authenticated') is True and state.get('modelSupported') is True:return provider
 raise RuntimeError('No provider passed installed, authentication and exact-model checks')
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--preflight-json',required=True);ap.add_argument('--output',required=True);ap.add_argument('--provider',choices=ORDER);a=ap.parse_args()
 output=pathlib.Path(a.output)
 if output.exists():
  existing=json.loads(output.read_text());print(json.dumps(existing));return
 flags=json.loads(pathlib.Path(a.preflight_json).read_text());chosen=select(flags,a.provider)
 output.parent.mkdir(parents=True,exist_ok=True)
 temp=output.with_suffix('.tmp');temp.write_text(json.dumps({'provider':chosen,'state':'selected'}));os.replace(temp,output)
 print(json.dumps({'provider':chosen}))
if __name__=='__main__':main()
