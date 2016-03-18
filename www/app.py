import logging
logging.basicConfig(level=logging.INFO)
import asyncio,os,json,time,orm
from aiohttp import web
from datetime import datetime
from jinja2 import Environment, FileSystemLoader
from coroweb import add_routes, add_static
from handler import __COOKIE_NAME,cookie2user


def init_jinja2(app, **kw):
    logging.info('init jinja2...')
    # 初始化模板配置，包括模板运行代码的开始结束标识符，变量的开始结束标识符等
    options = dict(
        # 是否转义设置为True，就是在渲染模板时自动把变量中的<>&等字符转换为&lt;&gt;&amp;
        autoescape=kw.get('autoescape', True),
        block_start_string=kw.get('block_start_string', '{%'),  # 运行代码的开始标识符
        block_end_string=kw.get('block_end_string', '%}'),  # 运行代码的结束标识符
        variable_start_string=kw.get('variable_start_string', '{{'),  # 变量开始标识符
        variable_end_string=kw.get('variable_end_string', '}}'),  # 变量结束标识符
        # Jinja2会在使用Template时检查模板文件的状态，如果模板有修改， 则重新加载模板。如果对性能要求较高，可以将此值设为False
        auto_reload=kw.get('auto_reload', True)
    )
    # 从参数中获取path字段，即模板文件的位置
    path = kw.get('path', None)
    # 如果没有，则默认为当前文件目录下的 templates 目录
    if path is None:
        path = os.path.join(os.path.dirname(
            os.path.abspath(__file__)), 'templates')
    logging.info('set jinja2 template path: %s' % path)
    # Environment是Jinja2中的一个核心类，它的实例用来保存配置、全局对象，以及从本地文件系统或其它位置加载模板。
    # 这里把要加载的模板和配置传给Environment，生成Environment实例
    env = Environment(loader=FileSystemLoader(path), **options)
    # 从参数取filter字段
    # filters: 一个字典描述的filters过滤器集合, 如果非模板被加载的时候, 可以安全的添加filters或移除较早的.
    filters = kw.get('filters', None)
    # 如果有传入的过滤器设置，则设置为env的过滤器集合
    if filters is not None:
        for name, f in filters.items():
            env.filters[name] = f
    # 给webapp设置模板
    app['__templating__'] = env


def datetime_filter(t):
    delta = int(time.time() - t)
    if delta < 60:
        return u'1分钟前'
    if delta < 3600:
        return u'%s分钟前' % (delta // 60)
    if delta < 86400:
        return u'%s小时前' % (delta // 3600)
    if delta < 604800:
        return u'%s天前' % (delta // 86400)
    dt = datetime.fromtimestamp(t)
    return u'%s年%s月%s日' % (dt.year, dt.month, dt.day)

# 定义middleware函数


@asyncio.coroutine
def logger_factory(app, handler):
    @asyncio.coroutine
    def logger(request):
        logging.info('Request: %s, %s' % (request.method, request.path))
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
            resp = web.Response(body=r)
            resp.content_type = 'application/object-stream'
            return resp

        if isinstance(r, str):
            if r.startswith('redirect'):
                return web.HTTPFound(r[9:])
            resp = web.Response(body=r.encode('utf-8'))
            resp.content_type = 'text/html;charset=utf-8'
            return resp

        if isinstance(r, dict):
            template = r.get('__template__')
            if template is None:
                resp = web.Response(body=json.dumps(r, ensure_ascii=False, default=lambda o: o.__dict__).encode('utf-8'))
                resp.content_type = 'application/json;charset=utf-8'
                return resp
            else:
                r['__user__'] = request.__user__
                resp = web.Response(body=app['__templating__'].get_template(template).render(**r).encode('utf-8'))
                resp.content_type = 'text/html;charset=utf-8'
                return resp
        if isinstance(r, int) and r >= 100 and r < 600:
            return web.Response(t)

        if isinstance(r, tuple) and len(r) == 2:
            t, m = r
            if isinstance(t, int) and t >= 100 and t < 600:
                return web.Response(status=t, text=str(m))

        resp = web.Response(body=str(r).encode('utf-8'))
        resp.content_type = 'text/plain;charset = utf-8'
        return resp
    return response

#每个url进行处理，判断cookie信息，并从中获取用户
@asyncio.coroutine
def auth_factory(app,handler):
    @asyncio.coroutine
    def auth(request):
        logging.info('check user info: %s %s ' %(request.method,request.path))
        request.__user__ = None
        cookie_str = request.cookies.get(__COOKIE_NAME)

        print("**********cookie_str = %s" %cookie_str)
        if cookie_str:
            user = yield from cookie2user(cookie_str)
            if user:
                request.__user__ = user
        if request.path.startswith('/manage/') and (request.__user__ is None or not request.__user__.admin):
            return web.HTTPFound('/signin')
        return (yield from handler(request))
    return auth


@asyncio.coroutine
def init(loop):
    yield from orm.create_pool(loop=loop)

    app = web.Application(loop=loop, middlewares=[
                          logger_factory,auth_factory,response_factory])

    init_jinja2(app, filters=dict(datetime=datetime_filter))
    add_routes(app, 'handler')
    add_static(app)
    srv = yield from loop.create_server(app.make_handler(), '127.0.0.1', '8000')
    logging.info('server started at http://127.0.0.1:9000')
    return srv

loop = asyncio.get_event_loop()
loop.run_until_complete(init(loop))

loop.run_forever()
