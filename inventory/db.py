from sqlalchemy import create_engine, event
from sqlalchemy.orm import joinedload, sessionmaker

from .models import *


item_with_category_association = joinedload(Item.categories)
item_with_categories = item_with_category_association \
    .joinedload(CategoryItemAssociation.category)

category_with_item_association = joinedload(Category.items)
category_with_items = category_with_item_association \
    .joinedload(CategoryItemAssociation.item)


def connect(app):
    """Connects to the specific database."""
    url = app.config['DATABASE']
    engine = create_engine(url, echo=True)
    Session = sessionmaker(bind=engine)

    # Enable foreign keys for SQLite
    if url.startswith('sqlite://'):
        def on_connect(conn, record):
            conn.execute('pragma foreign_keys=ON')

        event.listen(engine, 'connect', on_connect)

    return engine, Session


def get(app, g):
    """Opens a singleton database connection for the current application
    context.
    """
    if not hasattr(g, 'db_engine'):
        g.db_engine, g.db_Session = connect(app)
    return g.db_engine, g.db_Session


def init(app, g):
    """Initializes the application database."""
    engine, _ = get(app, g)
    Base.metadata.create_all(engine)


def load_sample_data(app, g, data):
    """Loads sample data into the database."""
    _, Session = get(app, g)
    session = Session()

    # Create categories
    categories = []
    for fields in reversed(data['categories']):
        category = Category(**fields)
        session.add(category)
        categories.append(category)

    # Create items
    associations = []
    for fields in reversed(data['items']):
        category_title = fields.pop('_category', None)

        item = Item(**fields)

        if category_title:
            for category in categories:
                if category.title == category_title:
                    associations.append((category, item))
                    break

        session.add(item)

    session.commit()

    # Add associations
    for category, item in associations:
        assoc = CategoryItemAssociation(category_id=category.id,
                                        item_id=item.id)
        session.add(assoc)

    session.commit()
