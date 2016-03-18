import re, time, json, logging, hashlib, base64, asyncio
import markdown

from coroweb import get, post
from model import User, Comment, Blog, next_id
from apis import APIValueError, APIError, APIPermissionError,APIResourceNotFoundError,Page
from aiohttp import web


_RE_EMAIL = re.compile(r'^[a-z0-9\.\-\_]+\@[a-z0-9\-\_]+(\.[a-z0-9\-\_]+){1,4}$')
_RE_SHA1 = re.compile(r'^[0-9a-f]{40}$')

__COOKIE_KEY = 'AwEsOmE'
__COOKIE_NAME = 'awesession'

#校验用户是否是admin
def check_admin(request):
	if request.__user__ is None or request.__user__.admin:
		return APIPermissionError()

#把存文本文件转为html格式的文本
def text2html(text):
	lines = map(lambda s: '<p>%s</p>' % s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'), filter(lambda s: s.strip() != '', text.split('\n')))
	return ''.join(lines)

# build cookie string as : id-expires-sha1
def user2cookie(user, max_age):
	expires = str(int(time.time() + max_age))

	s = '%s-%s-%s-%s' %(user.id, user.passwd, expires, __COOKIE_KEY)
	L = [user.id, expires, hashlib.sha1(s.encode('utf-8')).hexdigest()]

	return '-'.join(L)

#解析COOKIE信息，加载用户
@asyncio.coroutine
def cookie2user(cookie_str):
	if not cookie_str:
		return None
	try:
		L = cookie_str.split('-')
		if len(L) != 3:
			return None
		uid,expires,sha1 = L
		if int(expires) < time.time():
			return None
		user = yield from User.find(uid)
		if user is None:
			return None
		s = '%s-%s-%s-%s' %(uid,user.passwd,expires,__COOKIE_KEY)
		if sha1 != hashlib.sha1(s.encode('utf-8')).hexdigest():
			return None
		user.passwd = '******'
		return user
	except Exception as e:
		return None
#获取页面索引；将str类型转化为int类型，并校验索引合法性：
def get_page_index(page_str):
    p = 1
    try:
        p = int(page_str)
    except ValueError as e:
        pass
    if p < 1:
        p = 1
    return p

#首页测试
@get('/')
def index(request):
	#users = yield from User.findAll()
	if request.__user__:
		user = request.__user__
	else:
		user = None
	blogs = yield from Blog.findAll()
	return {
		'__template__':'blogs.html',
		#'users':users
		'blogs':blogs,
		'user':user
	}

#-------------------------------users action------------------------

#user login
@get('/signin')
def signin():
	return {
		'__template__':'signin.html'
	}

#user information authenticate
@post('/api/authenticate')
def authenticate(*,email,passwd):
	if not email:
		raise APIValueError('email','invalid email')
	if not passwd:
		raise APIValueError('passwd','invalid passwd')
	users = yield from User.findAll('email=?',[email])
	if len(users)<0:
		return APIValueError('email','Email is not exist')

	user = users[0]
	sha1 = hashlib.sha1()
	sha1.update(user.id.encode('utf-8'))
	sha1.update(b':')
	sha1.update(passwd.encode('utf-8'))
	if user.passwd != sha1.hexdigest():
		raise APIValueError('passwd','invalid passwd')

	r = web.Response()
	
	r.set_cookie(__COOKIE_NAME,user2cookie(user,86400),max_age = 86400, httponly = True)

	user.passwd = '******'
	r.content_type = 'application/json'
	r.body = json.dumps(user, ensure_ascii = False).encode('utf-8')

	return r

#user logout
@get('/signout')
def signout(request):
	referer = request.headers.get('Referer')
	r = web.HTTPFound(referer or '/')
	#清理掉cookie得用户信息数据
	r.set_cookie(__COOKIE_NAME, '-deleted-', max_age=0, httponly=True)
	logging.info('user signed out')
	return r

#user register url
@get('/register')
def register():
	return {
		'__template__':'register.html'
	}

#user register handle
@post('/api/users')
def api_register_user(*,email,name,passwd):
	if not name or not name.strip():
		raise APIValueError('name')
	if not email or not _RE_EMAIL.match(email):
		raise APIValueError('email')
	if not passwd or not _RE_SHA1.match(passwd):
		raise APIValueError('passwd')

	users = yield from User.findAll('email = ?', [email])
	print(users)
	if len(users) > 0:
		raise APIError('register:failed', 'email', 'Email is already in use')

	uid = next_id()

	sha1_passwd = '%s:%s' %(uid, passwd)

	admin = False
	if email == 'admin@163.com':
		admin = True

#-------------------------------users action end------------------------


#-------------------------------blog action-----------------------------

#view blog
@get('/blog/{id}')
def get_blog(id):
	blog = yield from Blog.find(id)
	comments = yield from Comment.findAll('blog_id=?',[id], orderBy='created_at desc')
	
	for c in comments:
		c.html_content = text2html(c.content)
	blog.html_content = markdown.markdown(blog.content)
	
	return {
		'__template__':'blog.html',
		'blog':blog,
		'comments':comments
	}

#manage blog url
@get('/manage/blogs')
def manage_blogs(*, page = '1'):
	return {
		'__template__':'manage_blogs.html',
		'page_index': get_page_index(page)
	}

#create blog url
@get('/manage/blogs/create')
def manage_create_blog():
	return {
		'__template__':'manage_blog_edit.html',
		'id':'',
		'action':'/api/blogs'
	}

#create or edit blog
@get('/manage/blogs/edit')
def manage_edit_blog(*, id):
	return {
		'__template__':'manage_blog_edit.html',
		'id':id,
		'action':'/api/blogs/%s' %id
	}

#指定内容(博客)展示 URL处理函数：
@get('/api/blogs/{id}')
def api_get_blog(*, id):
    blog = yield from Blog.find(id)
    return blog

#指定索引页内容(博客)展示 URL处理函数：
@get('/api/blogs')
def api_blogs(*, page='1'):
    page_index = get_page_index(page)
    
    num = yield from Blog.findNumber('count(id)')
    p = Page(num, page_index)
    if num == 0:
        return dict(page=p, blogs=())
    
    blogs = yield from Blog.findAll(orderBy='created_at desc', limit=(p.offset, p.limit))
    return dict(page=p, blogs=blogs)

#新建修改blog
@post('/api/blogs')
def api_create_blogs(request,*,name,summary,content):
	check_admin(request)
	if not name or not name.strip():
		raise APIValueError('name','name can not be empty')
	if summary is None or not summary.strip():
		raise APIValueError('summary','summary can not be empty')
	if content is None or not content.strip():
		raise APIValueError('content', 'content can not be empty')

	blog = Blog(user_id = request.__user__.id, user_name = request.__user__.name, user_image = request.__user__.image, name = name.strip(), summary = summary.strip(), content = content.strip())
	yield from blog.save()

	return blog

#-------------------------------blog action end----------------------------

#管理中心
@get('/manage/')
def manage():
	return 'redirect:/manage/comments'


#------------------------------manage comments ------------------------
#评论管理
@get('/manage/comments')
def manage_comments(*, page = '1'):
	return {
		'__template__':'manage_comments.html',
		'page_index':get_page_index(page)
	}

#指定索引页评论展示 URL处理函数：
@get('/api/comments')
def api_comments(*, page='1'):
    #获取页面索引，默认为1：
    page_index = get_page_index(page)
    #查询数据库中Comment表中评论总数：
    num = yield from Comment.findNumber('count(id)')
    p = Page(num, page_index)
    if num == 0:
        return dict(page=p, comments=())
    comments = yield from Comment.findAll(orderBy='created_at desc', limit=(p.offset, p.limit))
    return dict(page=p, comments=comments)

#删除制定的comment
@get('/api/comments/{id}/delete')
def api_comments_delete(id, request):
	check_admin(request)
	c = yield from Comment.find(id)

	if c is None:
		raise APIResourceNotFoundError('comments')

	yield from c.remove
	return dict(id = id)


#对某个博客发表评论
@post('/api/blogs/{id}/comments')
def api_create_comment(id, request, *, content):
	user = request.__user__
	#必须为登陆状态下，评论
	if user is None:
		raise APIPermissionError('content')
	#评论不能为空
	if not content or not content.strip():
		raise APIValueError('content')
	#查询一下博客id是否有对应的博客
	blog = yield from Blog.find(id)
	#没有的话抛出错误
	if blog is None:
		raise APIResourceNotFoundError('Blog')
	#构建一条评论数据
	comment = Comment(blog_id=blog.id, user_id=user.id, user_name=user.name, user_image=user.image, content=content.strip())
	#保存到评论表里
	yield from comment.save()
	return comment

#------------------------------manage comments end------------------------



#------------------------------manage users ------------------------

#用户管理页面
@get('/manage/users')
def manage_users(*, page='1'):
	return {
		'__template__':'manage_users.html',
		'page_index':get_page_index(page)
	}



	user = User(id = uid, name = name.strip(), email = email, passwd = hashlib.sha1(sha1_passwd.encode('utf-8')).hexdigest(), image = 'http://www.gravatar.com/avatar/%s?d=mm&s=120' % hashlib.md5(email.encode('utf-8')).hexdigest(), admin = admin)
	yield from user.save()
	logging.info('save user ok')

	r = web.Response()

	r.set_cookie(__COOKIE_NAME,user2cookie(user, 86400))

	user.passwd = '******'
	r.content_type = 'application/json'

	r.body = json.dumps(user, ensure_ascii =False).encode('utf-8')

	return r


#返回所有的用户信息
@get('/api/users')
def api_get_users(request):
	users = yield from User.findAll(orderBy='created_at desc')
	logging.info('users = %s and type = %s' % (users, type(users)))
	for u in users:
		u.passwd = '******'
	return dict(users=users)

#------------------------------manage users end------------------------