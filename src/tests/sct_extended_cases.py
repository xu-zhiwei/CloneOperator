"""Nontrivial compiler/execution fixtures for the family implementations."""
# Each item is (strategy ID, constructor options, method). Original and variant
# run with the same inputs. No fixture may pass by returning unchanged source.
EXTENDED_CASES = [
    (
        "WI1",
        {"selection": "last"},
        "int m(){int result=0;{int x=1;result+=x;}{int x=2;result+=x;}return result;}",
    ),
    ("WI1", {}, "int m(){int sum=0;for(int i=0;i<3;i++){sum+=i;}return sum;}"),
    (
        "WI1",
        {"candidate_source": "vocabulary", "token_vocab": ["alpha", "beta"]},
        "int m(int a){return Math.abs(a);}",
    ),
    ("WC1", {"modes": ["multiply_one"]}, "long m(){return -9223372036854775808L;}"),
    ("WC2", {}, "long m(){return (1L * 7L);}"),
    ("WC3", {"mode": "random"}, "int m(){return -2147483648;}"),
    ("WC5", {"offsets": [2, 4]}, "long m(){return -9223372036854775808L;}"),
    ("SE1", {}, "long m(int a){long b=2147483648L;return a+b;}"),
    ("SE2", {"modes": ["xor_zero"]}, "long m(){long a=9223372036854775807L;return a;}"),
    ("SE3", {}, "long m(){long a=9223372036854775807L;return 0L+a;}"),
    ("SE4", {}, "boolean m(int a){long b=2147483648L;return a<b;}"),
    (
        "SE5",
        {"mode": "compound"},
        "long m(){long x=9223372036854775807L;x++;return x;}",
    ),
    ("SE6", {"operators": ["^="]}, "long m(int a){long x=2147483648L;x^=a;return x;}"),
    (
        "SD1",
        {"enabled_reorders": ["non_adjacent_decl_run"], "max_distance": 4},
        "int m(){int a=1;int b=2;int c=3;return a+b+c;}",
    ),
    (
        "SD1",
        {"enabled_reorders": ["adjacent_multi_decl"]},
        "int m(){int a=1,b=2;int c=3,d=4;return a+b+c+d;}",
    ),
    ("SD2", {"java_types": ["String"]}, "int m(int a){if(a>0){a++;}return a;}"),
    ("SD3", {}, "int m(int a){int dead=2,live=a+1;return live;}"),
    ("SD4", {}, "long m(int a){long x=a,y=x+1;return y;}"),
    ("SD4", {}, "boolean m(){boolean x=true;return x;}"),
    ("SD5", {"max_distance": 3}, "int m(){int x;int y=2;x=3;return x+y;}"),
    ("SS1", {"max_distance": 3}, "int m(int a,int b){a++;int c=2;b+=3;return a+b+c;}"),
    ("SS2", {"modes": ["inc_dec"], "java_types": ["long"]}, "int m(){return 1;}"),
    ("SS2", {"modes": ["dec_inc"], "java_types": ["int"]}, "int m(){return 1;}"),
    ("SS3", {}, "int m(int a){long dead=0L;a+=2;dead++;a+=3;dead=dead*2;return a;}"),
    (
        "SS4",
        {"extract": "subexpressions"},
        "long m(int a){long b=2147483648L;return (b+a)*2L;}",
    ),
    ("SS4", {"selection": "first"}, "int m(int a){int x=(a+1)*2;return x;}"),
    ("SS5", {"max_distance": 3}, "int m(int a){int tmp=a+1;int b=2;return tmp*b;}"),
    (
        "CC1",
        {"mode": "reverse"},
        "int m(int a){switch(a){case 0:{int x=1;return x;}case 1:return 2;default:return 3;}}",
    ),
    (
        "CC1",
        {"mode": "all_pairs"},
        'int m(int a){switch(a){case 0:System.out.print("A");return 1;case 1:System.out.print("B");return 2;default:return 3;}}',
    ),
    ("CC2", {"modes": ["dead_else"]}, "int m(){return 1;}"),
    ("CC3", {}, "int m(){if(!false){return 1;}else{return 2;}}"),
    ("CC3", {}, "int m(){if(false && true){return 2;}return 1;}"),
    ("CC8", {}, "int m(int a){int b=0;if(a>0 && ++b>0 && ++b<4){b+=2;}return b;}"),
    (
        "CC9",
        {},
        "int m(int a){int b=0;if(a>0){if(++b>0){if(a<2){b=3;}else{b=4;}}}return b;}",
    ),
    ("CC10", {}, "int m(int a){if(++a>0){a=1;}else if(a<0){a=2;}else{a=3;}return a;}"),
    ("CL1", {"modes": ["for"]}, "int m(){return 1;}"),
    ("CL2", {}, "int m(){int x=1;for(int i=2;i<0;i++){x++;}return x;}"),
    (
        "CL2",
        {},
        "int m(){int x=0;boolean flag=false;int y=1;while(flag){x++;}return x+y;}",
    ),
    ("CL7", {}, "int m(){int x;do{x=1;}while(x<0);return x;}"),
    ("CL7", {}, "int m(){do{return 1;}while(false);}"),
    ("CL7", {}, "int m(int a){if(a>0){do{return 1;}while(a>1);}else{return 2;}}"),
    (
        "CL7",
        {},
        "int m(){int x=0;outer:do{x++;if(x<3)continue outer;break outer;}while(x<4);return x;}",
    ),
    (
        "CL7",
        {},
        "int m(){int x=0;do{for(int j=0;j<2;j++){if(j==0)continue;x++;}}while(x<3);return x;}",
    ),
    (
        "CL7",
        {},
        "int m(){int x=0;do{try{x++;continue;}finally{x++;}}while(x<4);return x;}",
    ),
    ("CL7", {"mode": "first_flag"}, "int m(){int x=0;do{x++;}while(x<2);return x;}"),
    ("CL8", {}, "int m(){while(1<2){return 1;}}"),
    (
        "CL8",
        {},
        "int m(){int x=0;outer:while(x<3){x++;if(x<2)continue outer;break outer;}return x;}",
    ),
    (
        "CL8",
        {"mode": "condition_at_start"},
        "int m(int a){int x=0;while(++a<3){x++;if(x>3)break;continue;}return x;}",
    ),
]

EXTENDED_CASES += [
    ("CL7", {}, "int m(){do{try{return 1;}finally{}}while(false);}"),
    ("CL7", {}, "int m(){int x=0;do{try{x++;continue;}finally{return x;}}while(x<3);}"),
    (
        "CL7",
        {},
        "int m(int a){do{switch(a){case 1:return 1;default:return 2;}}while(a>0);}",
    ),
    (
        "CL7",
        {},
        "int m(){int x=0;do{x++;switch(x){case 1:continue;case 2:break;default:break;}}while(x<3);return x;}",
    ),
]

EXTENDED_CASES += [
    ("SD4", {}, "int m(int a){int x=Math.abs(a);return x;}"),
    (
        "SD4",
        {},
        'int m(){java.util.List<String> xs=new java.util.ArrayList<>();xs.add("x");return xs.size();}',
    ),
    ("SD4", {}, "int m(){int a[][]={{1},{2}};return a[1][0];}"),
    ("SD4", {}, "int m(){byte a=(1+2)*3;return a;}"),
    ("SD5", {}, "int m(int a){String x;x=String.valueOf(a);return x.length();}"),
]
