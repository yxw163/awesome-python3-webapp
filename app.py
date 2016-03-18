import logging; logging.basicConfig(level = logging.INFO)
import asyncio,os,json,time
from aiohttp import web
from datetime import datetime


#定义middleware函数
@asyncio.coroutine
def logger_factory(app, handler):
	@asyncio.coroutine
	def logger(request):
		logging.info('Request: %s, %s' %(request.method, request.path))
		return (yield from handler(request))
	return logger

@asyncio.coroutine
def response_factory(app, handler):
	@asyncio.coroutine
	def response(request):
		logging.info('Response handler....')

		r = yield from handler(request)
		if isinstance(r, web.StreamResponse):
			return r

		if isinstance(r, bytes):
			resp = web.Response(body = r)
			resp.content_type = 'application/object-stream'
			return resp

		if isinstance(r, str):
			if r.startswith('redirect'):
				return web.HTTPFound(r[9:])
			resp = web.Response(body = r.encode('utf-8'))
			resp.content_type = 'text/html;charset=utf-8'
			return resp

		if isinstance(r, dict):
			template = r.get('__template__')
			if template is None:
				resp = web.Response(body = json.dump(body=json.dumps(r, ensure_ascii=False, default=lambda o: o.__dict__).encode('utf-8')))
				resp.content_type = 'application/json;charset=utf-8'
			else:
				r['__user__'] = request.__user__
				resp = web.Response(body=app['__templating__'].get_template(template).render(**r).encode('utf-8'))
				resp.content_type = 'text/html;charset=utf-8'
				return resp
		if isinstance(r, int) and r >=100 and r < 600:
			return web.Response(t)

		if isinstance(r, tuple) and len(r) ==2:
			t,m = r
			if isinstance(t, int) and t >= 100 and t < 600:
				return web.Response(status = t, text = str(m))
			resp = web.Response(body = str(r).encode('utf-8'))
			resp.content_type = 'text/plain;charset = utf-8'
			return resp
	return response

def index(request):
	return web.Response(body = b'<h1>Awesome</h1>')

@asyncio.coroutine
def init(loop):
	app = web.Application(loop = loop)
	app.router.add_route('GET','/',index)
	srv = yield from loop.create_server(app.make_handler(),'127.0.0.1','9000')
	logging.info('server started at http://127.0.0.1:9000')
	return srv

loop = asyncio.get_event_loop()
loop.run_until_complete(init(loop))

loop.run_forever()