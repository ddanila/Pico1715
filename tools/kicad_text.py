"""Small lossless node filter for KiCad/Specctra text; retains original tokens."""
import re
TOKEN=re.compile(r'"(?:\\.|[^"\\])*"|[()]|[^\s()]+')
def remove_nodes(source,predicate):
 stack=[];cuts=[]
 for m in TOKEN.finditer(source):
  t=m.group()
  if t=='(':stack.append([m.start(),None])
  elif t==')':
   start,head=stack.pop()
   if predicate(head,source[start:m.end()],len(stack)):
    cuts=[r for r in cuts if not start<=r[0]<m.end()];cuts.append((start,m.end()))
  elif stack and stack[-1][1] is None:stack[-1][1]=t
 assert not stack
 for a,z in sorted(cuts,reverse=True):source=source[:a]+source[z:]
 return source
