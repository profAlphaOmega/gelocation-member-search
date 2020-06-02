'''Migrate old HQ data to the new schema

This script is kindof ugly as hell. Hopefully you'll never actually need to
update it or use it ever again!
'''
from __future__ import print_function

import MySQLdb as mysqldb
import re
import sqlalchemy
import sys
import traceback
import yaml
from collections import defaultdict
from datetime import date, datetime
from pprint import pprint, pformat
from sqlalchemy import create_engine, MetaData

class MigrateException(Exception): pass
class AbortMember(Exception): pass

COUNTRY_MAP = {
    'united states': 'US',
    'afghanistan': 'AF',
    'aland islands': 'AX',
    'albania': 'AL',
    'algeria': 'DZ',
    'american samoa': 'AS',
    'andorra': 'AD',
    'angola': 'AO',
    'anguilla': 'AI',
    'antarctica': 'AQ',
    'antigua and barbuda': 'AG',
    'argentina': 'AR',
    'armenia': 'AM',
    'aruba': 'AW',
    'australia': 'AU',
    'austria': 'AT',
    'azerbaijan': 'AZ',
    'azores': 'AZX',
    'bahamas': 'BS',
    'bahrain': 'BH',
    'bangladesh': 'BD',
    'barbados': 'BB',
    'belarus': 'BY',
    'belgium': 'BE',
    'belize': 'BZ',
    'benin': 'BJ',
    'bermuda': 'BM',
    'bhutan': 'BT',
    'bolivia': 'BO',
    'bosnia and herzegovina': 'BA',
    'botswana': 'BW',
    'bouvet island': 'BV',
    'brazil': 'BR',
    'british indian ocean territory': 'IO',
    'brunei darussalam': 'BN',
    'bulgaria': 'BG',
    'burkina faso': 'BF',
    'burundi': 'BI',
    'cambodia': 'KH',
    'cameroon': 'CM',
    'canada': 'CA',
    'canary islands': 'CIX',
    'cape verde': 'CV',
    'cayman islands': 'KY',
    'central african republic': 'CF',
    'chad': 'TD',
    'chile': 'CL',
    'china': 'CN',
    'christmas island': 'CX',
    'cocos (keeling) islands': 'CC',
    'colombia': 'CO',
    'comoros': 'KM',
    'congo': 'CG',
    'congo, the democratic republic of the': 'CD',
    'cook islands': 'CK',
    'costa rica': 'CR',
    'cote d\'ivoire': 'CI',
    'croatia': 'HR',
    'cuba': 'CU',
    'cyprus': 'CY',
    'czech republic': 'CZ',
    'denmark': 'DK',
    'djibouti': 'DJ',
    'dominica': 'DM',
    'dominican republic': 'DO',
    'ecuador': 'EC',
    'egypt': 'EG',
    'el salvador': 'SV',
    'equatorial guinea': 'GQ',
    'eritrea': 'ER',
    'estonia': 'EE',
    'ethiopia': 'ET',
    'falkland islands (malvinas)': 'FK',
    'faroe islands': 'FO',
    'fiji': 'FJ',
    'finland': 'FI',
    'france': 'FR',
    'french guiana': 'GF',
    'french polynesia': 'PF',
    'french southern territories': 'TF',
    'gabon': 'GA',
    'gambia': 'GM',
    'georgia': 'GE',
    'germany': 'DE',
    'ghana': 'GH',
    'gibraltar': 'GI',
    'greece': 'GR',
    'greenland': 'GL',
    'grenada': 'GD',
    'guadeloupe': 'GP',
    'guam': 'GU',
    'guatemala': 'GT',
    'guernsey': 'GG',
    'guinea': 'GN',
    'guinea-bissau': 'GW',
    'guyana': 'GY',
    'haiti': 'HT',
    'heard island and mcdonald islands': 'HM',
    'holy see (vatican city state)': 'VA',
    'honduras': 'HN',
    'hong kong': 'HK',
    'hungary': 'HU',
    'iceland': 'IS',
    'india': 'IN',
    'indonesia': 'ID',
    'iran, islamic republic of': 'IR',
    'iraq': 'IQ',
    'ireland': 'IE',
    'isle of man': 'IM',
    'israel': 'IL',
    'italy': 'IT',
    'jamaica': 'JM',
    'japan': 'JP',
    'jersey': 'JE',
    'jordan': 'JO',
    'kazakhstan': 'KZ',
    'kenya': 'KE',
    'kiribati': 'KI',
    'korea, democratic people\'s republic of': 'KP',
    'korea, republic of': 'KR',
    'kuwait': 'KW',
    'kyrgyzstan': 'KG',
    'lao people\'s democratic republic': 'LA',
    'latvia': 'LV',
    'lebanon': 'LB',
    'lesotho': 'LS',
    'liberia': 'LR',
    'libyan arab jamahiriya': 'LY',
    'liechtenstein': 'LI',
    'lithuania': 'LT',
    'luxembourg': 'LU',
    'macao': 'MO',
    'macedonia, the former yugoslav republic of': 'MK',
    'madagascar': 'MG',
    'malawi': 'MW',
    'malaysia': 'MY',
    'maldives': 'MV',
    'mali': 'ML',
    'malta': 'MT',
    'marshall islands': 'MH',
    'martinique': 'MQ',
    'mauritania': 'MR',
    'mauritius': 'MU',
    'mayotte': 'YT',
    'mexico': 'MX',
    'micronesia, federated states of': 'FM',
    'moldova': 'MD',
    'monaco': 'MC',
    'mongolia': 'MN',
    'montenegro': 'ME',
    'montserrat': 'MS',
    'morocco': 'MA',
    'mozambique': 'MZ',
    'myanmar': 'MM',
    'namibia': 'NA',
    'nauru': 'NR',
    'nepal': 'NP',
    'netherlands': 'NL',
    'netherlands antilles': 'AN',
    'new caledonia': 'NC',
    'new zealand': 'NZ',
    'nicaragua': 'NI',
    'niger': 'NE',
    'nigeria': 'NG',
    'niue': 'NU',
    'norfolk island': 'NF',
    'northern ireland': 'NIX',
    'northern mariana islands': 'MP',
    'norway': 'NO',
    'oman': 'OM',
    'pakistan': 'PK',
    'palau': 'PW',
    'palestinian territory, occupied': 'PS',
    'panama': 'PA',
    'papua new guinea': 'PG',
    'paraguay': 'PY',
    'peru': 'PE',
    'philippines': 'PH',
    'pitcairn': 'PN',
    'poland': 'PL',
    'portugal': 'PT',
    'puerto rico': 'PR',
    'qatar': 'QA',
    'reunion': 'RE',
    'romania': 'RO',
    'russian federation': 'RU',
    'rwanda': 'RW',
    'saint barthelemy': 'BL',
    'saint helena': 'SH',
    'saint kitts and nevis': 'KN',
    'saint lucia': 'LC',
    'saint martin': 'MF',
    'saint pierre and miquelon': 'PM',
    'saint vincent and the grenadines': 'VC',
    'samoa': 'WS',
    'san marino': 'SM',
    'sao tome and principe': 'ST',
    'saudi arabia': 'SA',
    'scotland': 'SCX',
    'senegal': 'SN',
    'serbia': 'RS',
    'seychelles': 'SC',
    'sierra leone': 'SL',
    'singapore': 'SG',
    'slovakia': 'SK',
    'slovenia': 'SI',
    'solomon islands': 'SB',
    'somalia': 'SO',
    'south africa': 'ZA',
    'south georgia and the south sandwich islands': 'GS',
    'spain': 'ES',
    'sri lanka': 'LK',
    'sudan': 'SD',
    'suriname': 'SR',
    'svalbard and jan mayen': 'SJ',
    'swaziland': 'SZ',
    'sweden': 'SE',
    'switzerland': 'CH',
    'syrian arab republic': 'SY',
    'taiwan': 'TW',
    'tajikistan': 'TJ',
    'tanzania, united republic of': 'TZ',
    'thailand': 'TH',
    'timor-leste': 'TL',
    'togo': 'TG',
    'tokelau': 'TK',
    'tonga': 'TO',
    'trinidad and tobago': 'TT',
    'tunisia': 'TN',
    'turkey': 'TR',
    'turkmenistan': 'TM',
    'turks and caicos islands': 'TC',
    'tuvalu': 'TV',
    'uganda': 'UG',
    'ukraine': 'UA',
    'united arab emirates': 'AE',
    'united states minor outlying islands': 'UM',
    'united kingdom': 'GB',
    'uruguay': 'UY',
    'uzbekistan': 'UZ',
    'vanuatu': 'VU',
    'venezuela': 'VE',
    'viet nam': 'VN',
    'virgin islands, british': 'VG',
    'virgin islands, u.s.': 'VI',
    'wales': 'WAX',
    'wallis and futuna': 'WF',
    'western sahara': 'EH',
    'yemen': 'YE',
    'zambia': 'ZM',
    'zimbabwe': 'ZW',

    'usa': 'US',
    'russia': 'RU',
    'england': 'GB',
    'uk': 'GB',
    'taiwan   republic of china': 'TW',
    'iran': 'IR',
    'south korea': 'KR',
    'cayman islands   bwi': 'KY',
    'tahiti   french polynesia': 'PF',
    'taiwan': 'TW',
    'holland': 'NL',
    'colombi': 'CO',
    'korea south': 'KR',
}

DB = {
    'host': 'db.aavso.org',
    'user': 'aavso_web',
    'passwd': 'vstar',
    'db': 'oldhq'
}
DB_URI = 'mysql+mysqldb://aavso_web:vstar@db.aavso.org/oldhq?charset=utf8'

class MemberErrors(object):
    errors = {}

    def log(self, memberid, field, value, message='invalid value'):
        if not self.errors.get(memberid):
            self.errors[memberid] = []
        self.errors[memberid].append({
            "field": field, 
            "value": value, 
            "message": message
        })

    def __str__(self):
        return unicode(self).encode('utf8')

    def __unicode__(self):
        text = ''
        for id in sorted(self.errors.keys()):
            text += "Member #" + str(id) + "\n"

            for error in self.errors[id]:
                text += u"  {field}: {value} -- {message}\n".format(**error)
            text += '\n'

        return text

member_errors = MemberErrors()

def init():
    engine = create_engine(DB_URI)
    meta = MetaData(bind=engine)
    meta.reflect()
    return meta

def organizations(meta):
    engine = meta.bind
    org_t = meta.tables['organization']

    result = engine.execute(org_t.select())

    data = []
    for row in result:
        data.append({ 
            'model': 'hq.organization',
            'pk': int(row.affiliation),
            'fields': {
                'name': row.orgname,
                'abbreviation': row.abbreviation.strip().upper(),
            },
        })

    return data

def certifications(meta):
    engine = meta.bind
    cert_t = meta.tables['certifications']

    result = engine.execute(cert_t.select())

    data = []
    for row in result:
        data.append({
            'model': 'hq.certification',
            'pk': int(row[cert_t.c.id]),
            'fields': {
                'name': row[cert_t.c.name],
            },
        })

    return data

def obs_awards(meta):
    awards = [
        'Visual',
        'CCD',
        'PEP',
        'Photographic',
        'Solar',
        'SID',
    ]

    data = []
    for award,id in zip(awards, range(1, len(awards)+1)):
        data.append({
            'model': 'hq.obsaward',
            'pk': id, 
            'fields': {
                'name': award,
            },
        })

    return data

def has_nonascii(text):
    for ch in text:
        if ord(ch) > 127:
            return True
    return False

def t(text):
    text = text or ''
    text = text.strip()
    return text

def titlize(text, id, field):
    text = t(text)
    
    if text.isupper() or text.islower() and len(text.strip('.')) > 1:
        member_errors.log(id, field, text, 'field has been title-cased')
        text = text.title()
    return text

used_obscodes = []
def generate_member(row, payments):
    if payments:
        latest = max(payments, key=lambda x: int(x.Year[:4]))
    else:
        latest = defaultdict(lambda: None)
        member_errors.log(row.memberID, 'payments', '', 
            'member had no associated payments')

    id = int(row.memberID)

    member = {
        'model': 'hq.member',
        'pk': id,
        'fields': {
            # obscode below
            'title': titlize(row.title, id, 'title'),
            # given name below
            'middle_name': titlize(row.middle_name, id, 'middle_name'),
            # family_name below
            'name_suffix': titlize(row.name_suffix, id, 'name_suffix'),

            'organization': titlize(row.name_ext, id, 'organization'),
            'address1': titlize(row.address, id, 'address1'),
            'address2': titlize(row.address_ext, id, 'address2'),
            'city': titlize(row.city, id, 'city'),
            'region': t(row.state),
            'postal': t(row.zip),
            # country below
            'phone1': t(row.phone1),
            'phone2': t(row.phone2),
            'email': t(row.email).lower(),
            'email_optout': bool(row.email_optout),

            # special membership below
            'created': row.Created or date(1900,1,1), # default value
            'updated': row.Updated or date.today(),
            'observer_added': row.date_observer_added or None,
            'member_joined': row.date_joined or None,
            'astronomer': bool(latest['Astronomer']),
            'institution': bool(latest['Institution']),
            'council': bool(latest['Council']),
            'staff': False,
            'address_invalid': bool(latest['Invalid_Address']),
            'deceased': bool(latest['deceased']),
            'solar_observer': bool(latest['solar_observer']),
            'notes': t(row.note),
            'observer_notes': t(row.obsnotes),

            'profession': t(row.profession),
            'affiliation_id': int(row.affiliation or 0),
            'nickname': t(row.nickname),
            # birthdate below
            'howheard': t(row.howheard),
            'experience': t(row.experience),
            'member_notes': t(row.member_notes),
        },
    }

    ### obscode ###
    if row.obscode:
        obscode = row.obscode.strip()
        if re.match(r'^[A-Z0-9]{1,6}$', obscode):
            if obscode in used_obscodes:
                member_errors.log(row.memberID, 'obscode', row.obscode,
                    "Duplicate obscode--omitting from this record")
            else:
                used_obscodes.append(obscode)
                member['fields']['obscode'] = obscode
        else:
            member_errors.log(row.memberID, 'obscode', row.obscode)

    ### given_name ###
    first_name = t(row.first_name)
    if first_name:
        member['fields']['given_name'] = titlize(first_name, id, 'given_name')
    else:
        member['fields']['given_name'] = '.'
        member_errors.log(row.memberID, 'given_name', '', 
            'member has no first name to export -- set to default (.)')

    ### family_name ###
    last_name = t(row.last_name)
    if last_name:
        member['fields']['family_name'] = titlize(last_name, id, 'family_name')
    else:
        member_errors.log(row.memberID, 'last_name', '', 
            'ABORTED: member has no last name to export')
        raise AbortMember("No last name!")

    ### country ###
    if row.country:
        code = COUNTRY_MAP.get(row.country.lower(), None)
        if code is None:
            member_errors.log(row.memberID, 'country', row.country, 
                'unknown country')
        else:
            member['fields']['country'] = code

    ### birthdate ###
    if row.birthdate:
        ambig_fmts = [
            '%m/%d/%Y',
            '%d/%m/%Y',

            '%m-%d-%Y',
            '%d-%m-%Y',

            '%m.%d.%Y',
            '%d.%m.%Y',
        ]
        fmts = [
            '%Y/%m/%d',
            '%Y-%m-%d',
            '%Y.%m.%d',

            '%B %d, %Y',
            '%b %d, %Y',
            '%B %d %Y',
            '%b %d %Y',
            '%d %B %Y',
            '%d %b %Y',
        ]

        bd = None
        text = row.birthdate.strip()

        # check against unambiguous formats
        for fmt in fmts:
            try:
                bd = datetime.strptime(text, fmt).date()
                break
            except ValueError:
                continue

        if bd:
            member['fields']['birthdate'] = bd
        else: # check against ambiguous formats
            for fmt in ambig_fmts:
                try:
                    bd = datetime.strptime(text, fmt).date()
                    break
                except ValueError:
                    continue

            if bd:
                if bd.day <= 12 and bd.month <= 12:
                    pass
                    #member_errors.log(row.memberID, 'birthdate', 
                    #    row.birthdate, "birthdate is ambiguous")
                else:
                    member['fields']['birthdate'] = bd
            else: # didn't match any formats
                pass
                #member_errors.log(row.memberID, 'birthdate', row.birthdate,
                #    "couldn't parse birthdate")

    ### special_membership ###
    if latest['membership_type'] == 'H':
        member['fields']['special_membership'] = 'honorary'
    if latest['membership_type'] == 'L':
        member['fields']['special_membership'] = 'lifetime'

    ### Check for non-ascii characters and log them ###
    for field in member['fields']:
        txt = member['fields'][field]
        if isinstance(txt, basestring) and has_nonascii(txt):
            member_errors.log(row.memberID, field, txt, 
                'Field contains non-ascii characters')

    return member

def generate_payments(member, payments, paid_2011):
    data = []
    ### payments ###
    for payment in payments:
        new_payment = {
            'model': 'hq.payment',
            'pk': None,
            'fields': {
                'member_id': member['pk'],
                'amount': 0,
            },
        }

        if (payment.membership_type in ('N', 'H', 'L')):
            # not a payment if it's for non-member, honorary, lifetime
            continue

        ### type ###
        if payment.membership_type == 'R':
            typ = 'sponsored'
        elif payment.membership_type == 'M':
            typ = 'comp'
        elif payment.limited_income:
            if not payment.paid_membership:
                continue
            typ = 'junior'
        elif payment.membership_type == 'A':
            if not payment.paid_membership:
                continue
            typ = 'annual'
        elif payment.membership_type == 'S':
            if not payment.paid_membership:
                continue
            typ = 'sustaining'

        new_payment['fields']['type'] = typ

        ### begin/end ###
        years = payment.Year.split('-')

        # special for FYs2011-2012
        if payment.Year == '2010-2011':
            if member['pk'] in paid_2011:
                begin = date(2011, 1, 1)
                end = date(2011, 12, 31)
            else:
                begin = date(2010, 10, 1)
                end = date(2011, 9, 30)

        elif payment.Year == '2012':
            if member['pk'] in paid_2011:
                begin = date(2012, 1, 1)
            else: 
                begin = date(2011, 10, 1)
            end = date(2012, 12, 31)

        else:
            # one year, jan-dec
            if len(years) == 1:            
                year = int(years[0])
                begin = date(year, 1, 1)
                end = date(year, 12, 31)
            # two years, oct-sep
            else:
                begin, end = years
                begin = date(int(begin), 10, 1)
                end = date(int(end), 9, 30)

        new_payment['fields']['begin'] = begin
        new_payment['fields']['end'] = end

        data.append(new_payment)

    return data

def generate_sub_payments(member, payments):
    data = []
    ### subscription payments ###
    for payment in payments:
        if not payment.paid_subscriptions:
            continue 

        def new_payment():
            return {
                'model': 'hq.subscriptionpayment',
                'pk': None,
                'fields': {
                    'member_id': member['pk'],
                },
            }

        year = int(payment.Year[-4:])
        ### journal ###
        if payment.Journal or payment.Comp_Journal or payment.All_Pubs:
            jp = new_payment()
            jp['fields']['publication'] = 'journal'
            jp['fields']['paid'] = date(year, 1, 1)
            jp['fields']['year'] = year
            jp['fields']['complementary'] = bool(payment.Comp_Journal)
            data.append(jp)

        ### bulletin ###
        if payment.Bulletin or payment.All_Pubs:
            jp = new_payment()
            jp['fields']['publication'] = 'bulletin'
            jp['fields']['paid'] = date(year, 1, 1)
            jp['fields']['year'] = year
            jp['fields']['complementary'] = False
            data.append(jp)

        ### solar ###
        if payment.Solar_Bulletin or payment.Comp_Solar or payment.All_Pubs:
            jp = new_payment()
            jp['fields']['publication'] = 'solar'
            jp['fields']['paid'] = date(year, 1, 1)
            jp['fields']['year'] = year
            jp['fields']['complementary'] = bool(payment.Comp_Solar)
            data.append(jp)

        ### newsletter ###
        if payment.Paper_Newsletter or payment.All_Pubs:
            jp = new_payment()
            jp['fields']['publication'] = 'newsletter'
            jp['fields']['paid'] = date(year, 1, 1)
            jp['fields']['year'] = year
            jp['fields']['complementary'] = False
            data.append(jp)

        ### annual report ###
        if payment.All_Pubs:
            jp = new_payment()
            jp['fields']['publication'] = 'annual'
            jp['fields']['paid'] = date(year, 1, 1)
            jp['fields']['year'] = year
            jp['fields']['complementary'] = False
            data.append(jp)
    return data

def generate_member_certs(meta, member):
    engine = meta.bind
    cert_t = meta.tables['member_certifications']

    certs = engine.execute(cert_t.select()
        .where(cert_t.c.member_id == member['pk']))

    data = []
    for cert in certs:
        new_cert = {
            'model': 'hq.membercertification',
            'pk': None,
            'fields': {
                'member_id': member['pk'],
                'certification_id': int(cert.certification_id),
                'completed': cert.date_completed,
                'instructor': bool(cert.instructor),
            },
        }

        data.append(new_cert)
    return data

r_obsaward = re.compile(r'([0-9.]+)([kK]?)\s*(\d{4})')
def gen_obs_awards(row, history, typ):
    data = []
    awards = r_obsaward.findall(history)
    for award in awards:
        level = float(award[0])
        year = int(award[2])
        if award[1] in ('k', 'K'):
            level = int(level * 1000)

        data.append({
            'model': 'hq.memberobsaward',
            'pk': None,
            'fields': {
                'obs_award_id': typ,
                'member_id': int(row.memberID),
                'level': level,
                'year': year,
            },
        })
    return data

def generate_obs_awards(row):
    data = []

    if row.vis_award_history:
        data.extend(gen_obs_awards(row, row.vis_award_history, 1))
    if row.ccd_award_history:
        data.extend(gen_obs_awards(row, row.ccd_award_history, 2))
    if row.pep_award_history:
        data.extend(gen_obs_awards(row, row.pep_award_history, 3))
    if row.ptg_award_history:
        data.extend(gen_obs_awards(row, row.ptg_award_history, 4))
    if row.solar_award_history:
        data.extend(gen_obs_awards(row, row.solar_award_history, 5))

    return data


class Required(object): pass
table_fields = {
    'organization': (
        ('id', Required),
        ('name', Required),
        ('abbreviation', Required),
    ),
    'certification': (
        ('id', Required),
        ('name', Required),
    ),
    'obsaward': (
        ('id', Required),
        ('name', Required),
    ),
    'member': (
        ('id', Required),
        ('obscode', None),
        ('title', ''),
        ('given_name', Required),
        ('middle_name', ''),
        ('family_name', Required),
        ('name_suffix', ''),

        ('organization', ''),
        ('address1', ''),
        ('address2', ''),
        ('city', ''),
        ('region', ''),
        ('postal', ''),
        ('country', ''),
        ('phone1', ''),
        ('phone2', ''),
        ('email',''),
        ('email_optout',0),
        
        ('special_membership', ''),
        ('created', Required),
        ('updated', Required),
        ('observer_added', None),
        ('member_joined', None),
        ('astronomer', 0),
        ('institution', 0),
        ('council', 0),
        ('staff', 0),
        ('address_invalid', 0),
        ('resigned', 0),
        ('deceased', 0),
        ('solar_observer', 0),
        ('notes', ''),
        ('observer_notes', ''),

        ('latitude', None),
        ('longitude', None),
        ('profession', 0),
        ('affiliation_id', Required),
        ('nickname', ''),
        ('birthdate', None),
        ('howheard', ''),
        ('experience', ''),
        ('equipment', ''),
        ('member_notes', ''),
    ),
    'payment': (
        ('id', Required),
        ('member_id', Required), 
        ('type', Required), 
        ('amount', Required), 
        ('begin', Required),
        ('end', Required),
    ),

    'subscriptionpayment': (
        ('id', Required),
        ('member_id', Required),         
        ('publication', Required),
        ('paid', Required),
        ('year', Required),
        ('complementary', False),
    ),
    'membercertification': (
        ('id', Required),
        ('member_id', Required),
        ('certification_id', Required),
        ('completed', Required),
        ('instructor', Required),
    ),
    'memberobsaward': (
        ('id', Required),
        ('obs_award_id', Required),
        ('member_id', Required),
        ('level', Required),
        ('year', Required),
    ),
}

conn = mysqldb.connect(**DB)
def sqlize(val):
    if type(val) == unicode:
        val = val.encode('utf8')
    val = conn.escape(val)
    return str(val)

def generate_mysql(data):
    sql = '''INSERT INTO hq_{table} {fields} \nVALUES {values};\n\n'''
    ret = ''
    
    for table in data:
        rows = []
        for row in data[table]:
            vals = []
            for field in table_fields[table]:
                fname, default = field
                if fname == 'id':
                    val = row.get('pk', Required)
                else:
                    val = row['fields'].get(fname, default)

                if val == Required:
                    raise Exception("Field '{}' is required for table '{}':\n{}"
                        .format(fname, table, pformat(row)))

                vals.append(sqlize(val))
            rows.append('(' + ','.join(vals) + ')')

        QSIZE = 1000
        while len(rows):
            ret += sql.format(
                table=table,
                fields='(' + ','.join([t[0] for t in table_fields[table]]) + ')',
                values=',\n'.join(rows[:QSIZE]),
            )
            rows = rows[QSIZE:]

    return ret
        

def main(argv):
    meta = init()
    engine = meta.bind

    member_t = meta.tables['members']
    payment_t = meta.tables['payments']
    paid_2011_t = meta.tables['paid_2011']

    members = engine.execute(member_t.select()
        #.where(member_t.c.memberID == 17285)
    )
    paid_2011 = [x.member_id for x in engine.execute(paid_2011_t.select())
        .fetchall()]

    data = {
        'organization': [],
        'certification': [],
        'obsaward': [],
        'member': [],
        'payment': [],
        'subscriptionpayment': [],
        'membercertification': [],
        'memberobsaward': [],
    }
    data['organization'] = organizations(meta)
    data['certification'] = certifications(meta)
    data['obsaward'] = obs_awards(meta)
    total = 0
    processed = 0
    aborted = 0
    for row in members:
        total += 1
        ### get member's payments ###
        payments = engine.execute(payment_t.select()
            .where(payment_t.c.MemberID == row.memberID)).fetchall()

        try:
            member = generate_member(row, payments)
            #data['member'].append(member)

            #data['payment'].extend(
            #    generate_payments(member, payments, paid_2011))
            data['subscriptionpayment'].extend(
                generate_sub_payments(member, payments))
            #data['membercertification'].extend(
            #    generate_member_certs(meta, member))
            #data['memberobsaward'].extend(generate_obs_awards(row))

            processed +=1 

        except AbortMember as e:
            aborted +=1
            continue 

        except Exception as e:
            aborted +=1
            print("Exception processing Member #" + str(row.memberID), 
                file=sys.stderr)
            traceback.print_exc(file=sys.stderr)

    print("Total processed: " + str(total), file=sys.stderr)
    print("Successfully migrated: " + str(processed), file=sys.stderr)
    print("Aborted: " + str(aborted), file=sys.stderr)

    print(generate_mysql(data))
    print(member_errors, file=sys.stderr)

if __name__ == '__main__':
    main(sys.argv)
