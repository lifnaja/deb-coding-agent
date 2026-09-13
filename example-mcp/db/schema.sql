create table addresses (
    address_id uuid primary key,
    address text not null,
    zipcode text not null,
    state text not null,
    country text not null
);

create table promos (
    promo_id text primary key,
    discount numeric(5, 2) not null check (discount >= 0),
    status text not null
);

create table products (
    product_id uuid primary key,
    name text not null,
    price numeric(10, 2) not null check (price >= 0),
    inventory integer not null check (inventory >= 0)
);

create table users (
    user_id uuid primary key,
    first_name text not null,
    last_name text not null,
    email text not null unique,
    phone_number text not null,
    created_at timestamptz not null,
    updated_at timestamptz not null,
    address_id uuid not null references addresses (address_id)
);

create table orders (
    order_id uuid primary key,
    user_id uuid not null references users (user_id),
    promo_id text references promos (promo_id),
    address_id uuid not null references addresses (address_id),
    created_at timestamptz not null,
    order_cost numeric(10, 2) not null check (order_cost >= 0),
    shipping_cost numeric(10, 2) not null check (shipping_cost >= 0),
    order_total numeric(10, 2) not null check (order_total >= 0),
    tracking_id uuid,
    shipping_service text,
    estimated_delivery_at timestamptz,
    delivered_at timestamptz,
    status text not null
);

create table order_items (
    order_id uuid not null references orders (order_id),
    product_id uuid not null references products (product_id),
    quantity integer not null check (quantity > 0),
    primary key (order_id, product_id)
);

create table events (
    event_id uuid primary key,
    session_id uuid not null,
    user_id uuid not null references users (user_id),
    page_url text not null,
    created_at timestamptz not null,
    event_type text not null,
    order_id uuid references orders (order_id),
    product_id uuid references products (product_id)
);

\copy addresses from '/seed/addresses.csv' with (format csv, header true, null '');
\copy promos from '/seed/promos.csv' with (format csv, header true, null '');
\copy products from '/seed/products.csv' with (format csv, header true, null '');
\copy users from '/seed/users.csv' with (format csv, header true, null '');
\copy orders from '/seed/orders.csv' with (format csv, header true, null '');
\copy order_items from '/seed/order_items.csv' with (format csv, header true, null '');
\copy events from '/seed/events.csv' with (format csv, header true, null '');

select format(
    'create role %I login password %L',
    :'reader_user',
    :'reader_password'
)
where not exists (
    select 1
    from pg_roles
    where rolname = :'reader_user'
) \gexec

revoke create on schema public from public;
grant connect on database :"database_name" to :"reader_user";
grant usage on schema public to :"reader_user";
grant select on all tables in schema public to :"reader_user";
alter default privileges in schema public
    grant select on tables to :"reader_user";
alter role :"reader_user" set default_transaction_read_only = on;
alter role :"reader_user" set statement_timeout = '5s';
