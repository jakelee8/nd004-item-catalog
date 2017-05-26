from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, UnicodeText, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base


Base = declarative_base()


class Category(Base):
    """Inventory Category.

    Attributes:
        id: A unique integer representing the category.
        title: The category title.
    """
    __tablename__ = 'categories'
    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    title = Column(UnicodeText, nullable=False)

    items = relationship('CategoryItemAssociation', back_populates='category')

    def to_json(self):
        return {
            'id': self.id,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'title': self.title,
        }


class Item(Base):
    """Inventory Item.

    Attributes:
        id: A unique integer representing the item.
        title: The item title.
        summary: The item summary.
    """
    __tablename__ = 'items'
    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    title = Column(UnicodeText, nullable=False)
    summary = Column(UnicodeText)

    categories = relationship('CategoryItemAssociation',
                              back_populates='item')

    def to_json(self):
        return {
            'id': self.id,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'title': self.title,
            'summary': self.summary,
        }


class CategoryItemAssociation(Base):
    """Category-Item Association.

    Attributes:
        category_id: The category ID.
        item_id: The item ID.
    """
    __tablename__ = 'category_item_association'
    category_id = Column(Integer,
                         ForeignKey('categories.id', ondelete='CASCADE'),
                         primary_key=True)

    item_id = Column(Integer,
                     ForeignKey('items.id', ondelete='CASCADE'),
                     primary_key=True)

    category = relationship('Category', back_populates="items")
    item = relationship('Item', back_populates="categories")
