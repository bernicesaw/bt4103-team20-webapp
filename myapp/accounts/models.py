from django.db import models
from django.contrib.auth.models import User

# Full currency choices used for dropdowns. Values and labels match the provided list.
CURRENCY_CHOICES = [
    ('AED','AED'),('AFN','AFN'),('ALL','ALL'),('AMD','AMD'),('ANG','ANG'),('AOA','AOA'),('ARS','ARS'),('AUD','AUD'),
    ('AWG','AWG'),('AZN','AZN'),('BAM','BAM'),('BBD','BBD'),('BDT','BDT'),('BGN','BGN'),('BHD','BHD'),('BIF','BIF'),
    ('BMD','BMD'),('BND','BND'),('BOB BOV','BOB BOV'),('BRL','BRL'),('BSD','BSD'),('BWP','BWP'),('BYR','BYR'),('BZD','BZD'),
    ('CAD','CAD'),('CDF','CDF'),('CHF','CHF'),('CLP CLF','CLP CLF'),('CNY','CNY'),('COP COU','COP COU'),('CRC','CRC'),
    ('CUP CUC','CUP CUC'),('CVE','CVE'),('CZK','CZK'),('DJF','DJF'),('DKK','DKK'),('DOP','DOP'),('DZD','DZD'),
    ('EEK','EEK'),('EGP','EGP'),('ERN','ERN'),('ETB','ETB'),('EUR','EUR'),('FJD','FJD'),('FKP','FKP'),('GBP','GBP'),
    ('GEL','GEL'),('GHS','GHS'),('GIP','GIP'),('GMD','GMD'),('GNF','GNF'),('GTQ','GTQ'),('GYD','GYD'),('HKD','HKD'),
    ('HNL','HNL'),('HRK','HRK'),('HTG USD','HTG USD'),('HUF','HUF'),('IDR','IDR'),('ILS','ILS'),('INR','INR'),
    ('INR BTN','INR BTN'),('IQD','IQD'),('IRR','IRR'),('ISK','ISK'),('JMD','JMD'),('JOD','JOD'),('JPY','JPY'),
    ('KES','KES'),('KGS','KGS'),('KHR','KHR'),('KMF','KMF'),('KPW','KPW'),('KRW','KRW'),('KWD','KWD'),('KYD','KYD'),
    ('KZT','KZT'),('LAK','LAK'),('LBP','LBP'),('LKR','LKR'),('LRD','LRD'),('LTL','LTL'),('LVL','LVL'),('LYD','LYD'),
    ('MAD','MAD'),('MDL','MDL'),('MGA','MGA'),('MKD','MKD'),('MMK','MMK'),('MNT','MNT'),('MOP','MOP'),('MRO','MRO'),
    ('MUR','MUR'),('MVR','MVR'),('MWK','MWK'),('MXN MXV','MXN MXV'),('MYR','MYR'),('MZN','MZN'),('NGN','NGN'),
    ('NIO','NIO'),('NOK','NOK'),('NPR','NPR'),('NZD','NZD'),('OMR','OMR'),('PAB USD','PAB USD'),('PEN','PEN'),
    ('PGK','PGK'),('PHP','PHP'),('PKR','PKR'),('PLN','PLN'),('PYG','PYG'),('QAR','QAR'),('RON','RON'),('RSD','RSD'),
    ('RUB','RUB'),('RWF','RWF'),('SAR','SAR'),('SBD','SBD'),('SCR','SCR'),('SDG','SDG'),('SEK','SEK'),('SGD','SGD'),
    ('SHP','SHP'),('SLL','SLL'),('SOS','SOS'),('SRD','SRD'),('STD','STD'),('SVC USD','SVC USD'),('SYP','SYP'),
    ('SZL','SZL'),('THB','THB'),('TJS','TJS'),('TMT','TMT'),('TND','TND'),('TOP','TOP'),('TRY','TRY'),('TTD','TTD'),
    ('TWD','TWD'),('TZS','TZS'),('UAH','UAH'),('UGX','UGX'),('USD','USD'),('UYU UYI','UYU UYI'),('UZS','UZS'),
    ('VEF','VEF'),('VND','VND'),('VUV','VUV'),('WST','WST'),('XAF','XAF'),('XAG','XAG'),('XAU','XAU'),('XBA','XBA'),
    ('XBB','XBB'),('XBC','XBC'),('XBD','XBD'),('XCD','XCD'),('XDR','XDR'),('XFU','XFU'),('XOF','XOF'),('XPD','XPD'),
    ('XPF','XPF'),('XPT','XPT'),('XTS','XTS'),('YER','YER'),('ZAR','ZAR'),('ZAR LSL','ZAR LSL'),('ZAR NAD','ZAR NAD'),
    ('ZMK','ZMK'),('ZWL','ZWL')
]


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    job_title = models.CharField(max_length=200)
    skills = models.JSONField(default=list)  # list of skill strings, max 5 enforced in form
    median_salary = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=32, choices=CURRENCY_CHOICES, default='USD')
    # Whether the user has opted in to receive notifications from the app
    notifications_enabled = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.email} profile"


class WorkExperience(models.Model):
    profile = models.ForeignKey(Profile, related_name='work_experiences', on_delete=models.CASCADE)
    job_title = models.CharField(max_length=200)
    skills = models.JSONField(default=list)
    median_salary = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=32, choices=CURRENCY_CHOICES, default='USD')
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['order']