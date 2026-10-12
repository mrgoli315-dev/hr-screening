tpl=open('page.tpl.html').read(); data=open('data.js').read()
page=tpl.replace('/*DATA*/', data)
open('sales-hiring-shortlist.html','w').write(page)
s=page[page.index('<script>')+8:page.rindex('</script>')]
open('t.js','w').write(s)
head,rest=page.split('</style>',1)
open('MR_GOLISODA_Hiring_Shortlist.html','w').write('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'+head+'</style>\n</head>\n<body>\n'+rest+'\n</body>\n</html>\n')
print('bytes',len(page))
