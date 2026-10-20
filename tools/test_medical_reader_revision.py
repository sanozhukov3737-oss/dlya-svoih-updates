"""Guard adult first-aid scope and critical escalation/exception statements."""
import hashlib,json,re,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
DATA=json.loads((ROOT/'content/catalog.json').read_text())
CARDS={c['id']:c for c in DATA['cards']}
BATCH=json.loads((ROOT/'content/reader_part42_draft.json').read_text())
class MedicalReaderTests(unittest.TestCase):
 def article(self,suffix):return CARDS['first-aid-'+suffix]['body'].partition('\n\n## Служебные сведения')[0]
 def test_original_clinical_text_and_sources_are_retained(self):
  base={c['id']:c for c in json.loads((ROOT/'tools/medical_151_baseline.json').read_text())}
  med=[c for c in DATA['cards'] if c['section']=='MEDICINE']
  self.assertEqual(20,len(med))
  self.assertEqual({c['id'] for c in med},{e['id'] for e in BATCH['cards']})
  for c in med:
   old=base[c['id']];article,_,notes=c['body'].partition('\n\n## Служебные сведения')
   self.assertIn(old['body'],notes,c['id'])
   self.assertEqual(old['sources'],c['sources'],c['id'])
   self.assertEqual(old['images'],c['images'],c['id'])
   self.assertIn('заключение медицинского редактора не получено',notes,c['id'])
   self.assertEqual(3,len(re.findall(r'^## ',article,re.M)),c['id'])
 def test_resuscitation_and_airway_exceptions(self):
  cpr=self.article('adult-cpr')
  for text in ['100–120 в минуту','5–6 см','30 надавливаний и 2 вдоха','не переносите его с кровати на пол','детские алгоритмы отличаются']:
   self.assertIn(text,cpr)
  self.assertIn('сразу вызовите',cpr)
  aed=self.article('aed')
  for text in ['никто не должен касаться','даже если разряд не рекомендован','Электроды оставьте на месте']:
   self.assertIn(text,aed)
  recovery=self.article('unconscious')
  for text in ['не поворачивайте человека на бок автоматически','Проходимость дыхательных путей имеет приоритет','Если дыхание становится ненормальным, немедленно начинайте СЛР']:
   self.assertIn(text,recovery)
  primary=self.article('primary-assessment')
  self.assertIn('Не более 10 секунд',primary)
  self.assertIn('нельзя считать нормальными',primary)
 def test_bleeding_choking_and_trauma_exclusions(self):
  checks={
   'bleeding':['не ослабляйте жгут','если обучены','давите вокруг него','не исключает внутреннего'],
   'adult-choking':['до 5 ударов','до 5 толчков','после каждого','пальцами вслепую','при беременности'],
   'shock':['не поднимайте ноги','не давайте пищу или питьё'],
   'fracture':['внутрь её не возвращайте','Не выпрямляйте деформацию'],
   'head-injury':['минимум первые 24 часа','Если специалист разрешил','повторной рвоте'],
   'spinal-injury':['обеспечение дыхания имеет приоритет','Не выпрямляйте шею','без усилия'],
  }
  for suffix,terms in checks.items():
   for term in terms:self.assertIn(term,self.article(suffix),suffix)
 def test_burns_environment_and_observation_limits(self):
  checks={
   'burn':['не менее 20 минут','Прилипшую ткань не отрывайте','переохлаждения'],
   'eye-injury':['не менее 20 минут','продолжайте промывать','струя должна быть слабой','предмет не вытаскивайте'],
   'chemical-burn':['Сухой порошок сначала','не пытайтесь нейтрализовать','до прибытия помощи'],
   'electric-shock':['после подтверждённого отключения','не приближайтесь','нарушения сердечного ритма'],
   'seizure':['дольше 5 минут','ничего не вкладывайте в рот','без восстановления сознания'],
   'poisoning':['Не вызывайте рвоту','без указания специалиста','не входите'],
   'heat-illness':['Пот при нём может сохраняться','ничего не давайте через рот','начинайте охлаждение'],
   'hypothermia':['полностью бодрствующему','не растирайте конечности','Не используйте алкоголь'],
   'scene-safety':['Не входите в опасную зону','убедитесь, что вызов действительно сделан'],
   'handover':['изменении места ожидания','не завершайте разговор','неподтверждённого диагноза'],
  }
  for suffix,terms in checks.items():
   for term in terms:self.assertIn(term,self.article(suffix),suffix)
if __name__=='__main__':unittest.main()
