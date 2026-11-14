t=int(input())
for _ in range(t):
    a,b,c=map(int,input().split())
    d=(c-b)-(b-a)
    print("YES" if( d>=0 and d%3==0 )else "NO")