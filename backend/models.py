"""Request, reply, and product-card types for the chat agent."""

from typing import List, Literal, Optional

from pydantic import BaseModel, Field

MAX_MESSAGE_CHARS = 2000
MAX_HISTORY_TURNS = 20
MAX_PRODUCT_CARDS = 40


# ---------- What the agent returns ----------

class AgentReply(BaseModel):
    """Structured output the LLM must produce."""

    message: str = Field(description="The reply shown to the shopper, in the Campus Customs voice.")
    product_ids: List[str] = Field(
        default_factory=list,
        max_length=MAX_PRODUCT_CARDS,
        description=(
            "product_id values, exactly as returned by the tools, for the products to show as cards. "
            "For a category search, include every match from search_products, in the order it returned them. "
            "For a question about one or two products, include just those. Empty for small talk."
        ),
    )
    page_title: Optional[str] = Field(
        None,
        max_length=60,
        description=(
            "Set ONLY for catalogue searches / browsing (e.g. 'Hoodies', 'Navy crewnecks', 'Tees under $40'). "
            "When set, the site shows product_ids as a results grid on the page. "
            "Leave null for questions about a single product, stock, or small talk."
        ),
    )


# ---------- What the site sends / receives ----------

class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=8000)


class PageContext(BaseModel):
    """Where the shopper is on the site, sent by the front end with every chat message."""

    path: str = Field("/", max_length=300, description="Current URL path, e.g. /products/basic-hoodie-big-yale")
    results_title: Optional[str] = Field(None, max_length=60, description="Title of chat search results on the page, if any.")


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=MAX_MESSAGE_CHARS)
    # Used for guests only; logged-in history is loaded from chat_messages.
    history: List[ChatTurn] = Field(default_factory=list)
    page: Optional[PageContext] = None


class SizeStock(BaseModel):
    size: str
    quantity: int


class ProductCard(BaseModel):
    """A product card for the chat panel and the page results grid. Built from the database, not the LLM."""

    product_id: str
    name: str
    garment_type: str
    description: str
    price: float
    image_url: str
    colors: List[str]
    inventory: List[SizeStock]


class StoredChatMessage(BaseModel):
    """One saved chat_messages row as sent back to the site (cards re-read from the DB)."""

    id: int
    role: Literal["user", "assistant"]
    content: str
    products: List[ProductCard] = Field(default_factory=list)
    page_title: Optional[str] = None
    created_at: str


class ChatHistoryResponse(BaseModel):
    messages: List[StoredChatMessage]


# ---------- What the agent knows about the shopper (agent deps) ----------

class CustomerProfile(BaseModel):
    """The logged-in customer. Never includes the password hash."""

    first_name: Optional[str]
    last_name: Optional[str]
    name: str
    email: str
    member_since: str = Field(description="Account creation date (UTC).")


PageType = Literal["home", "products", "product", "about", "login", "signup", "other"]


class ViewingContext(BaseModel):
    """PageContext after the server has checked it against the database."""

    path: str
    page_type: PageType
    product_id: Optional[str] = None
    product_name: Optional[str] = None
    garment_type: Optional[str] = None
    results_title: Optional[str] = None


class ChatResponse(BaseModel):
    reply: str
    products: List[ProductCard] = Field(default_factory=list)
    page_title: Optional[str] = Field(
        None, description="If set, the front end shows `products` as a results grid on the Products page under this title."
    )


# ---------- What the tools return to the agent ----------
# Every number here comes straight from the catalogue / inventory tables.

LOW_STOCK_THRESHOLD = 5

StockStatus = Literal["in_stock", "low_stock", "sold_out"]


class ProductSummary(BaseModel):
    """One search hit: enough to pick a product, not the full story."""

    product_id: str
    name: str
    garment_type: str
    price: float = Field(description="Price in USD, exactly as stored.")
    colors: List[str]
    sizes_in_stock: List[str] = Field(description="Sizes with quantity > 0.")


class SearchResults(BaseModel):
    """search_products result. An explicit note keeps the model from re-running empty searches."""

    query: str
    count: int
    matches: List[ProductSummary]
    note: str


class ProductInfo(BaseModel):
    """search -> get_product_info: everything needed to describe a product and quote its price."""

    product_id: str
    name: str
    garment_type: str
    description: str
    price: float = Field(description="Price in USD, exactly as stored. Quote this, never estimate.")
    colors: List[str]
    sizes_in_stock: List[str]
    sold_out_sizes: List[str]
    total_in_stock: int


class SizeStockStatus(BaseModel):
    size: str
    quantity: int = Field(description="Units on hand for this size.")
    status: StockStatus


class SimilarItem(BaseModel):
    """A similar product that has the shopper's size in stock (out-of-stock fallback)."""

    product_id: str
    name: str
    garment_type: str
    price: float
    colors: List[str]
    quantity: int = Field(description="Units on hand in the requested size.")


class StockCheck(BaseModel):
    """check_stock: live inventory for one product, optionally focused on one size."""

    product_id: str
    name: str
    price: float
    requested_size: Optional[str] = Field(None, description="Normalized size asked about (XS-XXL), if any.")
    requested_size_offered: Optional[bool] = Field(None, description="False if the product doesn't come in that size at all.")
    requested_quantity: Optional[int] = Field(None, description="Units on hand in the requested size.")
    requested_status: Optional[StockStatus] = None
    stock_by_size: List[SizeStockStatus]
    sizes_in_stock: List[str]
    sold_out_sizes: List[str]
    total_in_stock: int
    closest_sizes_in_stock: List[SizeStockStatus] = Field(
        default_factory=list,
        description="If the requested size is sold out / not offered: in-stock sizes nearest to it, closest first.",
    )
    similar_in_stock: List[SimilarItem] = Field(
        default_factory=list,
        description="If the requested size is sold out / not offered: similar items that DO have that size.",
    )
    note: str = Field(description="Plain-language summary of the stock result, including the fallback to offer.")


class ProductNotFound(BaseModel):
    """Returned instead of ProductInfo / StockCheck when the product can't be pinned down."""

    error: str
    query: str
    suggestions: List[ProductSummary] = Field(
        default_factory=list, description="Close matches; ask the shopper which one, or retry with a product_id."
    )
