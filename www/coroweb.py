#-*- coding:utf-8 -*-

__author__ = 'yangxw'


import asyncio, os, inspect, logging, functools
from aiohttp import web
from apis import APIValueError, APIError
from urllib import parse


#logging.basicConfig(level=logging.INFO)

#创建修饰器，把url和处理函数做对应
def get(path):
	def decorator(func):
		@functools.wraps(func)
		def wrapper(*args, **kw):
			return func(*args, **kw)
		wrapper.__method__ = 'GET'
		wrapper.__path__ = path
		return wrapper
	return decorator

def post(path):
	def decorator(func):
		@functools.wraps(func)
		def wrapper(*args, **kw):
			return func(*args, **kw)
		wrapper.__method__ = 'POST'
		wrapper.__path__ = path
		return wrapper
	return decorator

# KEYWORD_ONLY表示函数参数类型为fun(*,a,b)
# 在使用函数时必须给关键字参数a,b进行传值即 fun(a = '22', b = '123')
def get_required_kw_args(fn):
	args = []
	params = inspect.signature(fn).parameters
	for name, param in params.items():
		if param.kind == inspect.Parameter.KEYWORD_ONLY and param.default == inspect.Parameter.empty:
			args.append(name)
	return tuple(args)

def get_named_kw_args(fn):
	args = []
	params = inspect.signature(fn).parameters
	for name, param in params.items():
		if param.kind == inspect.Parameter.KEYWORD_ONLY:
			args.append(name)
	return tuple(args)

def has_named_kw_args(fn):
	params = inspect.signature(fn).parameters
	for name,param in params.items():
		if param.kind == inspect.Parameter.KEYWORD_ONLY:
			return True

def has_var_kw_args(fn):
	params = inspect.signature(fn).parameters
	for name, param in params.items():
		if param.kind == inspect.Parameter.VAR_KEYWORD:
			return True

def has_request_args(fn):
	sig = inspect.signature(fn)
	params = inspect.signature(fn).parameters
	found = False
	for name, param in params.items():
		if name == 'request':
			found = True
			continue
		if found and (param.kind != inspect.Parameter.VAR_POSITIONAL and param.kind != inspect.Parameter.KEYWORD_ONLY and param.kind != inspect.Parameter.VAR_KEYWORD):
			raise ValueError('request parameter must be the last named parameter in function: %s%s' % (fn.__name__, str(sig)))
	return found


# 在调用URL处理函数前，处理函数的参数
class RequestHandler(object):
	"""docstring for RequestHandler"""
	def __init__(self, app, fn):
		self._app = app
		self._func = fn
		print("调用的函数: %s" % type(self._func))
		
		self._has_request_arg = has_request_args(fn)
		self._has_var_kw_arg = has_var_kw_args(fn)
		self._has_named_kw_arg = has_named_kw_args(fn)
		self._named_kw_args = get_named_kw_args(fn)
		self._required_kw_args = get_required_kw_args(fn)


	@asyncio.coroutine
	def __call__(self, request):
		kw = None
		logging.info(' %s : has_request_arg = %s,  has_var_kw_arg = %s, has_named_kw_args = %s, get_named_kw_args = %s, get_required_kw_args = %s ' % (__name__, self._has_request_arg, self._has_var_kw_arg, self._has_named_kw_arg,self._named_kw_args ,self._required_kw_args))
		if self._has_var_kw_arg or self._has_named_kw_arg or self._required_kw_args:
			if request.method == 'POST':
				if not request.content_type:
					return web.HTTPBadRequest('Missing content_type')

				ct = request.content_type.lower()

				if ct.startswith('application/json'):
					params = yield from request.json()
					if not isinstance(params, dict):
						return web.HTTPBadRequest('JSON Body must be object')

					kw = params

				elif ct.startswith('application/x-www-form-urlencoded') or ct.startswith('multipart/form-data'):
						params = yield from request.post()
						kw = dict(**params)
				else:
					return web.HTTPBadRequest('Unsupported Content-Type:%s' % request.content_type)

			if request.method == 'GET':
				qs = request.query_string
				logging.info('qs = %s' %qs)

				if qs:
					kw = dict()
					print(parse.parse_qs(qs, True))
					for k, v in parse.parse_qs(qs, True).items():
						kw[k] = v[0]
		
		if kw is None:
			kw = dict(**request.match_info)
		else:
			if not self._has_var_kw_arg and self._named_kw_args:
				copy = dict()
				for name in self._named_kw_args:
					if name in kw:
						copy[name] = kw[name]

				kw = copy

			for k,v in request.match_info.items():
				if k in kw:
					logging.warning('Duplicate arg name in named arg and kw args: %s' % k)
				kw[k] = v

		
		if self._has_request_arg:
			kw['request'] = request

		if self._required_kw_args:
			for name in self._required_kw_args:
				if not name in kw:
					return web.HTTPBadRequest('Missing argument: %s' % name)
			logging.info('call with args: %s' % str(kw))
		try:
			#对url进行处理
			
			r = yield from self._func(**kw)
			return r
		except APIError as e:
			return dict(error=e.error, data=e.data, message=e.message)


#添加静态页面的路径
def add_static(app):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
    app.router.add_static('/static/', path)
    logging.info('add static %s => %s' % ('/static/', path))

# 注册URL处理函数
def add_route(app, fn):
	method = getattr(fn, '__method__', None)
	path = getattr(fn, '__path__', None)
	if path is None or method is None:
		raise ValueError('@get or @ post not defined in %s.' % str(fn))
	if not asyncio.iscoroutinefunction(fn) and not inspect.isgeneratorfunction(fn):
		fn = asyncio.coroutine(fn)
	logging.info('exec in coroweb.py add_route: add route %s %s => %s(%s)' % (method, path, fn.__name__, ', '.join(inspect.signature(fn).parameters.keys())))

	app.router.add_route(method, path, RequestHandler(app, fn))


# 把handler.py里的所有处理函数进行注册
def add_routes(app, module_name):
	n = module_name.rfind('.')
	if n == (-1):
		mod = __import__(module_name,globals(),locals())
	else:
		mod = __import__(module_name[:n], globals(), locals())
	#print (dir(mod))
	for attr in dir(mod):
		if attr.startswith('_'):
			continue
		fn = getattr(mod, attr)
		if callable(fn):
			method = getattr(fn, '__method__', None)
			path = getattr(fn, '__path__', None)
			if method and path:
				add_route(app, fn)
