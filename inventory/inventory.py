import os
import yaml

from urllib.parse import urlunsplit

from flask import Flask
from flask import g, render_template, redirect, request, session, url_for
from flask import jsonify

from oauth2client.client import FlowExchangeError, OAuth2WebServerFlow

from sqlalchemy import desc

from . import db


def create_app():
    """Creates a Flask app."""
    app = Flask(__name__)

    # Load default config and override config from an environment variable
    app.config.update({
        'DATABASE': 'sqlite:////tmp/inventory.sqlite',
        'SECRET_KEY': 'secret',
        'USERNAME': 'admin',
        'PASSWORD': 'default',
        'GOOGLE_OAUTH_CLIENT_ID': '',
        'GOOGLE_OAUTH_CLIENT_SECRET': '',
    })
    app.config.from_envvar('INVENTORY_SETTINGS', silent=True)

    return app


app = create_app()


def load_sample_data():
    """Loads sample data into the database."""
    with app.open_resource('sample_data.yaml', 'r') as f:
        data = yaml.load(f.read())
    db.load_sample_data(app, g, data)


def initdb():
    """Initialize the database."""
    db.init(app, g)


@app.cli.command('initdb')
def initdb_command():
    """Initializes the database."""
    if app.debug:
        # Remove SQLite database during development.
        db_path = app.config['DATABASE']
        if db_path.startswith('sqlite:///'):
            db_path = db_path[10:]
            if os.path.exists(db_path):
                os.remove(db_path)

    # Initialize the database.
    initdb()

    # Load sample data during development.
    if app.debug:
        load_sample_data()

    print('Initialized the database.')


@app.teardown_appcontext
def close_db(error):
    """Closes the database again at the end of the request."""
    if hasattr(g, 'db_engine'):
        g.db_engine.dispose()


@app.errorhandler(404)
def page_not_found(error='Not found.'):
    return render_template('error.html', error=error), 404


@app.errorhandler(403)
def unauthorized(error='Unauthorized.'):
    return render_template('error.html', error=error), 403


@app.errorhandler(FlowExchangeError)
def oauth2_error(error):
    return render_template('error.html', error=error), 403


@app.errorhandler(Exception)
def server_error(error):
    return render_template('error.html', error=error), 500


def url_defaults(endpoint, values):
    """Set default values for URLs."""
    item = getattr(g, 'item', None)
    values.setdefault('item_id', item.id if item else None)
    category = getattr(g, 'category', None)
    values.setdefault('category_id', category.id if category else None)


app.url_defaults(url_defaults)


@app.route('/')
def index():
    """Handles the landing page."""
    return list_items()


def oauth2_flow(return_path):
    """Configures an OAuth2 web server flow for the current context."""
    redirect_uri = urlunsplit(['http', request.environ['HTTP_HOST'],
                               return_path, '', ''])

    client_id = app.config['GOOGLE_OAUTH_CLIENT_ID']
    client_secret = app.config['GOOGLE_OAUTH_CLIENT_SECRET']

    flow = OAuth2WebServerFlow(client_id=client_id,
                               client_secret=client_secret,
                               scope='openid',  # profile, email, openid
                               redirect_uri=redirect_uri)

    return flow


@app.route('/signin')
def signin():
    """Signs in a user."""
    flow = oauth2_flow(url_for('signin_callback'))
    auth_uri = flow.step1_get_authorize_url()
    return redirect(auth_uri)


@app.route('/signout')
def signout():
    """Signs out a user."""
    session.clear()
    return redirect(url_for('index'))


@app.route('/signin/callback')
def signin_callback():
    """Logs in a user."""
    error = request.args.get('error')
    if error:
        return oauth2_error(error)

    code = request.args.get('code')
    if not code:
        return oauth2_error('Unable to sign in.')

    flow = oauth2_flow(url_for('signin_callback'))
    credentials = flow.step2_exchange(request.args['code'])

    # user_id = '{}/{}'.format(
    #     credentials.id_token['iss'], credentials.id_token['sub'])
    user_id = 'guest'  # don't send user_id unencrypted over internet
    session['user_id'] = user_id

    return redirect(url_for('index'))


@app.route('/items')
@app.route('/items.<format>')
def list_items(format=None):
    """Handles the landing page."""

    # Create database session
    _, Session = db.get(app, g)
    session = Session()

    # Fetch items
    query = session.query(db.Item).options(db.item_with_categories)
    query = query.order_by(desc(db.Item.updated_at))
    # query = query.limit(10)
    items = query.all()

    # Return in JSON format
    if format == 'json':
        return jsonify(items=[it.to_json() for it in items])

    # Fetch categories
    query = session.query(db.Category).order_by(db.Category.title)
    # query = query.limit(10)
    categories = query.all()

    return render_template('index.html',
                           items=items,
                           categories=categories)


@app.route('/items/<int:item_id>')
@app.route('/categories/<int:category_id>/items/<int:item_id>')
@app.route('/items/<int:item_id>.<format>')
def view_item(item_id, category_id=None, format=None):
    """Views an item."""

    # Create database session
    _, Session = db.get(app, g)
    session = Session()

    # Fetch item
    query = session.query(db.Item).filter(db.Item.id == item_id)
    item = query.options(db.item_with_categories).first()
    if not item:
        return page_not_found()

    # Return in JSON format
    if format == 'json':
        categories = [it.category.to_json() for it in item.categories]
        return jsonify(item=item.to_json(), item_categories=categories)

    # Find category for prefix
    category = None
    if category_id:
        for assoc in item.categories:
            if assoc.category_id == category_id:
                category = assoc.category
                break

    # Configure url_for to add category prefix with item
    g.item = item
    g.category = category

    return render_template('items/view.html', item=item, category=category)


@app.route('/items/new')
@app.route('/categories/<int:category_id>/items/new')
def new_item(category_id=None):
    """Edits an item."""
    if not session.get('user_id'):
        return unauthorized()

    # Create database session
    _, Session = db.get(app, g)
    sess = Session()

    # Fetch all categories
    categories = sess.query(db.Category).order_by(db.Category.title).all()

    # Calculate item category ids
    item_category_ids = set()
    category = None
    if category_id:
        item_category_ids.add(category_id)
        for cat in categories:
            if cat.id == category_id:
                category = g.category = cat
                break

    # Configure url_for to add category prefix
    g.category = category

    return render_template('items/edit.html',
                           item=None,
                           category=category,
                           categories=categories,
                           item_category_ids=item_category_ids)


@app.route('/items/<int:item_id>/edit')
@app.route('/categories/<int:category_id>/items/<int:item_id>/edit')
def edit_item(item_id, category_id=None):
    """Edits an item."""
    if not session.get('user_id'):
        return unauthorized()

    # Create database session
    _, Session = db.get(app, g)
    sess = Session()

    # Fetch item
    query = sess.query(db.Item).filter(db.Item.id == item_id)
    item = query.options(db.item_with_category_association).first()
    if not item:
        return page_not_found()

    # Fetch all categories
    categories = sess.query(db.Category).order_by(db.Category.title).all()

    # Calculate item category ids
    item_category_ids = set(a.category_id for a in item.categories)

    # Find item category
    category = None
    if category_id:
        for assoc in item.categories:
            if assoc.category_id == category_id:
                category = assoc.category
                break

    # Configure url_for to add category prefix with item
    g.item = item
    g.category = category

    return render_template('items/edit.html',
                           item=item,
                           item_category_ids=item_category_ids,
                           categories=categories,
                           category=category)


@app.route('/items', methods=['POST'])
@app.route('/categories/<int:category_id>/items', methods=['POST'])
def create_item(category_id=None):
    """Creates an item."""
    if not session.get('user_id'):
        return unauthorized()

    # Create item
    item = db.Item()
    for key, value in request.form.items():
        if key != 'categories':
            setattr(item, key, value)

    # Create item categories
    for category_id in request.form.getlist('categories'):
        assoc = db.CategoryItemAssociation()
        assoc.category_id = category_id
        item.categories.append(assoc)

    # Create database session
    _, Session = db.get(app, g)
    sess = Session()

    # Persist item
    sess.add(item)
    sess.commit()

    return redirect(url_for('view_item',
                            item_id=item.id,
                            category_id=category_id))


@app.route('/items/<int:item_id>', methods=['POST', 'PUT'])
@app.route('/categories/<int:category_id>/items/<int:item_id>',
           methods=['POST', 'PUT'])
def update_item(item_id, category_id=None):
    """Updates an item."""
    if not session.get('user_id'):
        return unauthorized()

    # Support delete via form method overwrite
    method = request.form.get('_method', '').lower()
    if method == 'delete':
        return delete_item(item_id, category_id=category_id)

    # Create database session
    _, Session = db.get(app, g)
    sess = Session()

    # Fetch item
    query = sess.query(db.Item).filter(db.Item.id == item_id)
    item = query.options(db.item_with_category_association).first()
    if not item:
        return page_not_found()

    # Update item
    for key, value in request.form.items():
        if key != 'categories':
            setattr(item, key, value)

    # Update item categories
    new_categories = request.form.getlist('categories')
    if not new_categories:
        # Delete all associations
        for association in tuple(item.categories):
            sess.delete(association)
    else:
        new_categories = set(map(int, new_categories))
        old_categories = set(a.category_id for a in item.categories)

        # Delete removed associations
        del_categories = old_categories - new_categories
        for association in tuple(item.categories):
            if association.category_id in del_categories:
                sess.delete(association)

        # Add new associations
        add_categories = new_categories - old_categories
        for cat_id in add_categories:
            assoc = db.CategoryItemAssociation()
            assoc.category_id = cat_id
            item.categories.append(assoc)

    # Persist item
    sess.commit()

    return redirect(url_for('view_item',
                            item_id=item_id,
                            category_id=category_id))


@app.route('/items/<int:item_id>', methods=['DELETE'])
@app.route('/categories/<int:category_id>/items/<int:item_id>',
           methods=['DELETE'])
def delete_item(item_id, category_id=None):
    """Deletes an item."""
    if not session.get('user_id'):
        return unauthorized()

    # Create database session
    _, Session = db.get(app, g)
    sess = Session()

    # Delete item
    sess.query(db.Item).filter(db.Item.id == item_id).delete()
    sess.commit()

    if category_id:
        return redirect(url_for('view_category', category_id=category_id))
    else:
        return redirect(url_for('index'))


@app.route('/categories/<category_id>')
def view_category(category_id):
    """Views a category."""

    # Create database session
    _, Session = db.get(app, g)
    session = Session()

    # Fetch category
    query = session.query(db.Category).filter(db.Category.id == category_id)
    category = query.options(db.category_with_items).first()
    if not category:
        return page_not_found()

    # Configure url_for to add category prefix
    g.category = category

    return render_template('items/list.html',
                           category=category,
                           items=[a.item for a in category.items if a.item])


@app.route('/categories/new')
def new_category():
    """Creates a category."""
    if not session.get('user_id'):
        return unauthorized()
    return render_template('categories/edit.html', category=None)


@app.route('/categories/<int:category_id>/edit')
def edit_category(category_id):
    """Edits a category."""
    if not session.get('user_id'):
        return unauthorized()

    # Create database session
    _, Session = db.get(app, g)
    sess = Session()

    # Fetch category
    query = sess.query(db.Category)
    category = query.filter(db.Category.id == category_id).first()
    if not category:
        return page_not_found()

    # Configure url_for to add category prefix
    g.category = category

    return render_template('categories/edit.html', category=category)


@app.route('/categories', methods=['POST'])
def create_category():
    """Creates a category."""
    if not session.get('user_id'):
        return unauthorized()

    # Create category
    category = db.Category()
    for key, value in request.form.items():
        setattr(category, key, value)

    # Create database session
    _, Session = db.get(app, g)
    sess = Session()

    # Persist category
    sess.add(category)
    sess.commit()

    return redirect(url_for('view_category', category_id=category.id))


@app.route('/categories/<int:category_id>', methods=['POST', 'PUT'])
def update_category(category_id):
    """Updates a category."""
    if not session.get('user_id'):
        return unauthorized()

    # Support delete via form method overwrite
    method = request.form.get('_method', 'put').lower()
    if method == 'delete':
        return delete_category(category_id)

    # Create database session
    _, Session = db.get(app, g)
    sess = Session()

    # Fetch category
    query = sess.query(db.Category)
    category = query.filter(db.Category.id == category_id).first()
    if not category:
        return page_not_found()

    # Udpate category
    for key, value in request.form.items():
        setattr(category, key, value)

    sess.commit()

    return redirect(url_for('view_category', category_id=category_id))


@app.route('/categories/<int:category_id>', methods=['DELETE'])
def delete_category(category_id):
    """Deletes a category."""

    # Create database session
    _, Session = db.get(app, g)
    sess = Session()

    # Delete category
    sess.query(db.Category).filter(db.Category.id == category_id).delete()
    sess.commit()

    return redirect(url_for('index'))


if __name__ == '__main__':
    app.run()
