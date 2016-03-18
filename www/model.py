import time
import uuid
import orm
import asyncio
from orm import StringField, TextField, IntegerField, FloatField, BooleanField, Model


def next_id():
	return '%015d%s000' % (int(time.time() * 1000), uuid.uuid1().hex)


class User(Model):
	__table__ = 'users'

	id = StringField(primary_key=True, default=next_id, ddl='varchar(50)')
	email = StringField(ddl='varchar(50)')
	passwd = StringField(ddl='varchar(50)')
	admin = BooleanField()
	name = StringField(ddl='varchar(50)')
	image = StringField(ddl='varchar(50)')
	created_at = FloatField(default=time.time)


class Blog(Model):
	__table__ = 'blogs'

	id = StringField(primary_key=True, default=next_id, ddl='varchar(50)')
	user_id = StringField(ddl='varchar(50)')
	user_name = StringField(ddl='varchar(50)')
	user_image = StringField(ddl='varchar(50)')
	name = StringField(ddl='varchar(50)')
	summary = StringField(ddl='varchar(200)')
	content = TextField()
	created_at = FloatField(default=time.time)


class Comment(Model):
	__table__ = 'comments'

	id = StringField(primary_key=True, default=next_id, ddl='varchar(50)')
	blog_id = StringField(ddl='varchar(50)')
	user_id = StringField(ddl='varchar(50)')
	user_name = StringField(ddl='varchar(50)')
	user_image = StringField(ddl='varchar(500)')
	content = TextField()
	created_at = FloatField(default=time.time)


# @asyncio.coroutine
# def test(loop):
	
# 	yield from orm.create_pool(loop = loop)
# 	u = User(name='yxw', email='yangxiaowei_163@egfbank.com.cn',passwd='123', image='about:blank')
# 	yield from u.save()

# loop = asyncio.get_event_loop()
# loop.run_until_complete(test(loop))
# loop.close()


	
