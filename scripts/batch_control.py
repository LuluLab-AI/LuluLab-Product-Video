#!/usr/bin/env python3
"""Run up to 3 independent COMPLETE video workflows; segments stay sequential inside jobs."""
import concurrent.futures,subprocess,sys,argparse,json
MAX_CONCURRENT_VIDEO_WORKFLOWS=3
def run_one(cmd):
 p=subprocess.run(cmd,shell=False,text=True,capture_output=True)
 return {'command':cmd,'returncode':p.returncode,'stdout':p.stdout[-1000:],'stderr':p.stderr[-1000:]}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--commands-json',required=True,help='JSON array of argv arrays, one argv per complete video workflow');a=ap.parse_args()
 jobs=json.load(open(a.commands_json))
 if not isinstance(jobs,list) or not 1<=len(jobs)<=10 or any(not isinstance(c,list) or not c for c in jobs):raise ValueError('Expect 1-10 argv arrays')
 with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_CONCURRENT_VIDEO_WORKFLOWS) as pool: results=list(pool.map(run_one,jobs))
 print(json.dumps(results,ensure_ascii=False,indent=2));sys.exit(1 if any(x['returncode'] for x in results) else 0)
if __name__=='__main__':main()
