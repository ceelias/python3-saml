import tornado.ioloop
import tornado.web
import Settings
import tornado.httpserver
import tornado.httputil

from onelogin.saml2.auth import OneLogin_Saml2_Auth
from onelogin.saml2.settings import OneLogin_Saml2_Settings
from onelogin.saml2.utils import OneLogin_Saml2_Utils

##Global session info
session = {}

class Application(tornado.web.Application):
    def __init__(self):
        handlers = [
            (r"/", IndexHandler),
            (r"/attrs", AttrsHandler),
            (r"/metadata",MetadataHandler),
        ]
        settings = {
            "template_path": Settings.TEMPLATE_PATH,
            "saml_path": Settings.SAML_PATH,
        }
        tornado.web.Application.__init__(self, handlers, **settings)


class IndexHandler(tornado.web.RequestHandler):
    def post(self):
        req = prepare_tornado_request(self.request)
        auth = init_saml_auth(req)
        attributes = False
        paint_logout = False

        auth.process_response()
        errors = auth.get_errors()
        not_auth_warn = not auth.is_authenticated()

        if len(errors) == 0:
             session['samlUserdata'] = auth.get_attributes()
             session['samlNameId'] = auth.get_nameid()
             session['samlSessionIndex'] = auth.get_session_index()
             self_url = OneLogin_Saml2_Utils.get_self_url(req)
             if 'RelayState' in request.forms and self_url != request.forms['RelayState']:
                 return redirect(request.forms['RelayState'])

        if 'samlUserdata' in session:
            paint_logout = True
            if len(session['samlUserdata']) > 0:
                attributes = session['samlUserdata'].items()

        self.render('index.html',errors=errors,not_auth_warn=not_auth_warn,attributes=attributes,paint_logout=paint_logout)

    def get(self):
        req = prepare_tornado_request(self.request)
        auth = init_saml_auth(req)
        errors = []
        not_auth_warn = False
        success_slo = False
        attributes = False
        paint_logout = False

        if 'sso' in req['get_data']:
            return self.redirect(auth.login())
        elif 'sso2' in req['get_data']:
            return_to = '%s/attrs' % self.request.host
            #return_to = OneLogin_Saml2_Utils.get_self_url(req) + reverse('attrs')
            return self.redirect(auth.login(return_to))
        elif 'slo' in req['get_data']:
            name_id = None
            session_index = None
            if 'samlNameId' in session:
                name_id = session['samlNameId']
            if 'samlSessionIndex' in session:
                session_index = session['samlSessionIndex']

            return self.redirect(auth.logout(name_id=name_id, session_index=session_index))

        elif 'sls' in req['get_data']:
            dscb = lambda: session.clear() ## clear out the session
            url = auth.process_slo(request_id=request_id, delete_session_cb=dscb)
            errors = auth.get_errors()
            if len(errors) == 0:
                if url is not None:
                    return self.redirect(url)
                else:
                    success_slo = True

        if 'samlUserdata' in session:
            paint_logout = True
            if len(session['samlUserdata']) > 0:
                attributes = session['samlUserdata'].items()

        self.render('index.html',errors=errors,not_auth_warn=not_auth_warn,success_slo=success_slo,attributes=attributes,paint_logout=paint_logout)

class AttrsHandler(tornado.web.RequestHandler):
    def get(self):
        paint_logout = False
        attributes = False

        if 'samlUserdata' in session:
            paint_logout = True
            if len(session['samlUserdata']) > 0:
                attributes = session['samlUserdata'].items()

        self.render('attrs.html',paint_logout=paint_logout,attributes=attributes)

class MetadataHandler(tornado.web.RequestHandler):
    def get(self):
        req = prepare_tornado_request(request)
        auth = init_saml_auth(req)
        saml_settings = auth.get_settings()
        #saml_settings = OneLogin_Saml2_Settings(settings=None, custom_base_path=settings.SAML_FOLDER, sp_validation_only=True)
        metadata = saml_settings.get_sp_metadata()
        errors = saml_settings.validate_metadata(metadata)

        if len(errors) == 0:
            resp = HttpResponse(content=metadata, content_type='text/xml')
        else:
            resp = HttpResponseServerError(content=', '.join(errors))
        return resp

def prepare_tornado_request(request):
    result = {
        'https': 'on' if request == 'https' else 'off',
        'http_host': tornado.httputil.split_host_and_port(request.host)[0],
        'script_name': request.path,
        'server_port': tornado.httputil.split_host_and_port(request.host)[1],
        'get_data': request.arguments,
        'post_data': request.arguments,
        'query_string': request.query
    }
    return result

def init_saml_auth(req):
    auth = OneLogin_Saml2_Auth(req, custom_base_path=Settings.SAML_PATH)
    return auth

if __name__ == "__main__":
    app = Application()
    http_server = tornado.httpserver.HTTPServer(app)
    http_server.listen(8000)
    tornado.ioloop.IOLoop.instance().start()
