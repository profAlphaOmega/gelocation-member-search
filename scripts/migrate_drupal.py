'''Migrate drupal users to new unified Django users'''
from __future__ import unicode_literals
import MySQLdb as mysql
from MySQLdb import cursors
from contextlib import closing
from collections import defaultdict
from django.conf import settings
from hq import models

def drupal_connect():
    return closing(mysql.connect(
        cursorclass=cursors.DictCursor,
        charset='utf8',
        use_unicode=True,
        **settings.DRUPAL_DB))

def django_connect():
    return closing(mysql.connect(
        user=settings.DATABASES['default']['USER'],
        passwd=settings.DATABASES['default']['PASSWORD'],
        host=settings.DATABASES['default']['HOST'],
        db=settings.DATABASES['default']['NAME'],
        cursorclass=cursors.DictCursor,
        charset='utf8',
        use_unicode=True,
    ))

# User object was assigned to a record
migrate_link = {}
# Which memberid is assigned to the userid
migrate_reverse = {}

problems = {
    'badid': [],
    'doubleid': defaultdict(list),
    'badfk': [],
}

def drupal_users():
    with drupal_connect() as conn, conn as cursor:
        cursor.execute('SELECT * FROM users')
        for user in cursor.fetchall():
            print ("\nProcessing {} ({})"
                    .format(user['name'], user['uid'])
                    .encode('utf8'))
            # Skip anonymous user
            if user['uid'] == 0:
                print "Skipping anonymous user"
                continue

            # Check if user account is linked to Django record
            cursor.execute('''SELECT value FROM profile_values
                    WHERE fid=19 and uid=%s''', (user['uid'],))
            linkid = cursor.fetchone()
            linkid = (int(linkid['value']) 
                      if linkid and linkid['value'] else None)

            if user['pass'] and user['pass'][0] != '!':
                password = "md5$$" + user['pass']
            else:
                password = '!invalid'

            # Copy linked user data
            if linkid:
                problems['doubleid'][linkid].append(user)
                if migrate_link.get(linkid) is not None:
                    print "Linked id ({}) already assigned to {}".format(
                        linkid, migrate_link[linkid]['name'])
                    migrate_reverse[user['uid']] = linkid
                    continue

                try:
                    record = models.Person.objects.get(id=linkid)
                    record.username = user['name']
                    record.password = password
                    record.email_verified = True
                    record.save()

                    migrate_link[record.id] = user
                    migrate_reverse[user['uid']] = record.id
                    print "Copied to existing record #" + str(linkid)
                except models.Person.DoesNotExist:
                    problems['badid'].append({
                        'user': user['name'],
                        'uid': user['uid'],
                        'linkid': linkid,
                    })
                    print "Record #{} does not exist!".format(linkid)

            # Create new People for unlinked users
            # also mark them as having validated emails
            else:
                record = models.Person.objects.create(
                    username=user['name'],
                    password=password,
                    given_name='No',
                    family_name='Name',
                    email=user['mail'],
                    affiliation_id=0,
                    email_verified=True,
                )
                migrate_reverse[user['uid']] = record.id
                print 'Created new record'

        for p in problems['doubleid'].keys():
            if len(problems['doubleid'][p]) <= 1:
                del problems['doubleid'][p]


def django_permissions():
    # Migrate Django User permissions + groups
    with django_connect() as conn, conn as cur:
        for uid, person_id in migrate_reverse.iteritems():
            person = models.Person.objects.get(id=person_id)
            cur.execute('SELECT * FROM auth_user WHERE id=%s', (uid,))
            user = cur.fetchone()

            # transfer staff/superuser powers
            if user is None:
                continue
            if user['is_staff']:
                person.is_staff = True
            if user['is_superuser']:
                person.is_superuser = True
            person.save()

            # migrate groups
            query = '''INSERT IGNORE INTO hq_person_groups 
                SELECT NULL, {person_id}, group_id FROM auth_user_groups
                WHERE user_id = {uid}'''.format(
                    person_id=person_id,
                    uid=uid)
            cur.execute(query)

            # migrate user permissions
            query = '''INSERT IGNORE INTO hq_person_user_permissions 
                SELECT NULL, {person_id}, permission_id 
                FROM auth_user_user_permissions
                WHERE user_id = {uid}'''.format(
                    person_id=person_id,
                    uid=uid)
            cur.execute(query)


def copy_table(cur, table):
    cur.execute("DROP TABLE IF EXISTS {table}_old".format(table=table))
    cur.execute("RENAME TABLE {table} TO {table}_old".format(table=table))
    cur.execute("CREATE TABLE {table} LIKE {table}_old".format(table=table))

def rm_table(cur, table):
    cur.execute("DROP TABLE {table}_old".format(table=table))


def foreign_keys():
    # Migrate ForeignKeys that pointed to User
    fields = {
        'aavsonet_proposal': ('id', 'proposer_id', 'owner_id', 'body',
            'date_submitted', 'date_accepted', 'status', 'priority'),
        'aavsonet_comment': ('id', 'user_id', 'proposal_id', 'body',
            'date_submitted'),
        'emailsubs_datausage': ('id', 'user_id',),
        'meetings_registration': ('id', 'meeting_id', 'user_id', 'address',
            'city', 'state', 'postal', 'country', 'phone', 'arrival_date', 
            'arrival_time', 'depart_date', 'depart_time', 'list_optout',
            'reg_type', 'donation', 'comp', 'paid', 'submitted_date'),
        'mynewsflash_subscription': ('id', 'user_id', 'title', 'frequency',
            'format', 'star_names', 'min_mag', 'max_mag', 'max_age',
            'ignore_ft'),
    }
    keys = {
        'aavsonet_proposal': ('proposer_id', 'owner_id'),
        'aavsonet_comment': ('user_id',),
        'emailsubs_datausage': ('user_id',),
        'meetings_registration': ('user_id',),
        'mynewsflash_subscription': ('user_id',),
    }

    with django_connect() as conn, conn as cur:
        for table in keys:
            copy_table(cur, table)
            if len(keys[table]) == 1:
                for uid, person_id in migrate_reverse.iteritems():
                    fs = ','.join(str(person_id) if f in keys[table] else f 
                                  for f in fields[table])
                    query = """INSERT INTO {table}
                        SELECT {fields} FROM {table}_old
                        WHERE {field}={uid}""".format(
                            table=table,
                            fields=fs,
                            field=keys[table][0],
                            uid=uid,)
                    cur.execute(query) 
            else:
                cur.execute("SELECT * FROM {table}_old".format(table=table))
                for row in cur.fetchall():
                    try:
                        values = [migrate_reverse[row[f]]
                                  if f in keys[table] else row[f]
                                  for f in fields[table]]
                        query = "INSERT INTO {table} VALUES ({fields})".format(
                            table=table, fields=','.join(['%s'] * len(values)))
                        cur.execute(query, values)
                    except KeyError:
                        problems['badfk'].append({
                            'table': table,
                            'row': row['id'],
                        })
            rm_table(cur, table)


def run():
    import warnings
    warnings.filterwarnings('ignore', category=mysql.Warning)
    drupal_users()
    django_permissions()
    foreign_keys()

    print "===== Problem Report ====="
    print "Bad Record links:"
    print ("These are Drupal users that have links to a Django record that"
           " doesn't exist. They have not been copied.")
    for p in problems['badid']:
        print "{user}({uid}) linked to {linkid}".format(**p).encode('utf8')
    print

    print "Double record links:"
    print "Django records that have two Drupal users linked to them."
    for linkid, users in problems['doubleid'].iteritems():
        print ("Record #{linkid} linked by multiple users: {users}"
            .format(linkid=linkid,
                users='; '.join("{name}({uid})".format(**u) for u in users),)
            .encode('utf8'))
    print

    print "Records with bad foreign keys:"
    for p in problems['badfk']:
        print "{table}: {row}".format(**p).encode('utf8')
