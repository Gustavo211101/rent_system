V1.0

Backup instruction:  

Make backup:   
python manage.py dumpdata --natural-foreign --natural-primary --indent 2 > backups/dump_$(date +%Y-%m-%d_%H-%M).json  

Restore backup:  
python manage.py loaddata backups/YOUR_dump.json  
  
All files in rent_system/backups  
  

Отдельно кладовщик, никто кроме него не редактирует оборудование✅  
Добавление персонала на мероприятие  
Импортирование оборудования из эксель  
В оборудовании понимание ‘ремонта’ отдельная вкладка и чтобы уменьшалось количество когда что-то чинится   
Довоз оборудования с причиной, отдельным пунктом  
Контроль того что приехало, контроль того что уехало  

Введение куар кода для отслеживания? перемещений  
