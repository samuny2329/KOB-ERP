/** WMS + Inventory API types and client helpers. */
import { api } from "@/lib/api";

// ── Types (mirror Pydantic Read schemas) ──────────────────────────────

export interface Warehouse {
  id: number;
  code: string;
  name: string;
  address: string | null;
  active: boolean;
}

export interface Zone {
  id: number;
  warehouse_id: number;
  code: string;
  name: string;
  color_hex: string | null;
  note: string | null;
  active: boolean;
}

export interface Uom {
  id: number;
  category_id: number;
  name: string;
  uom_type: string;
  factor: number;
  rounding: number;
  active: boolean;
}

export interface UomCategory {
  id: number;
  name: string;
}

export interface Location {
  id: number;
  warehouse_id: number | null;
  parent_id: number | null;
  zone_id: number | null;
  name: string;
  complete_name: string | null;
  usage: string;
  barcode: string | null;
  active: boolean;
}

export interface ProductCategory {
  id: number;
  parent_id: number | null;
  name: string;
  complete_name: string | null;
}

export interface Product {
  id: number;
  default_code: string;
  barcode: string | null;
  name: string;
  type: string;
  category_id: number | null;
  uom_id: number;
  list_price: number;
  standard_price: number;
  active: boolean;
  created_at: string;
}

export interface Lot {
  id: number;
  product_id: number;
  name: string;
  expiration_date: string | null;
  note: string | null;
}

export interface StockQuant {
  id: number;
  location_id: number;
  product_id: number;
  lot_id: number | null;
  quantity: number;
  reserved_quantity: number;
}

export interface TransferType {
  id: number;
  warehouse_id: number;
  code: string;
  name: string;
  direction: string;
  sequence_prefix: string;
  default_source_location_id: number | null;
  default_dest_location_id: number | null;
}

export interface TransferLine {
  id: number;
  transfer_id: number;
  product_id: number;
  uom_id: number;
  lot_id: number | null;
  source_location_id: number | null;
  dest_location_id: number | null;
  quantity_demand: number;
  quantity_done: number;
}

export interface Transfer {
  id: number;
  name: string;
  transfer_type_id: number;
  state: "draft" | "confirmed" | "done" | "cancelled";
  source_location_id: number;
  dest_location_id: number;
  origin: string | null;
  scheduled_date: string | null;
  done_date: string | null;
  note: string | null;
  lines: TransferLine[];
  created_at: string;
}

// ── API helpers ────────────────────────────────────────────────────────

export const wmsApi = {
  warehouses: () => api.get<Warehouse[]>("/wms/warehouses").then((r) => r.data),
  createWarehouse: (body: Pick<Warehouse, "code" | "name" | "address">) =>
    api.post<Warehouse>("/wms/warehouses", body).then((r) => r.data),

  zones: (warehouseId?: number) =>
    api.get<Zone[]>("/wms/zones", { params: { warehouse_id: warehouseId } }).then((r) => r.data),

  uoms: () => api.get<Uom[]>("/wms/uoms").then((r) => r.data),
  uomCategories: () => api.get<UomCategory[]>("/wms/uom-categories").then((r) => r.data),

  locations: (params?: { warehouse_id?: number; usage?: string }) =>
    api.get<Location[]>("/wms/locations", { params }).then((r) => r.data),

  products: (params?: { q?: string; limit?: number; offset?: number }) =>
    api.get<Product[]>("/wms/products", { params }).then((r) => r.data),
  createProduct: (body: {
    default_code: string;
    barcode?: string | null;
    name: string;
    type: "consu" | "service" | "product";
    category_id?: number | null;
    uom_id: number;
    list_price: number;
    standard_price: number;
  }) => api.post<Product>("/wms/products", body).then((r) => r.data),

  lots: (productId?: number) =>
    api.get<Lot[]>("/wms/lots", { params: { product_id: productId } }).then((r) => r.data),
};

export const inventoryApi = {
  quants: (params?: { location_id?: number; product_id?: number }) =>
    api.get<StockQuant[]>("/inventory/stock-quants", { params }).then((r) => r.data),

  transferTypes: (warehouseId?: number) =>
    api
      .get<TransferType[]>("/inventory/transfer-types", { params: { warehouse_id: warehouseId } })
      .then((r) => r.data),

  transfers: (params?: { state?: string; transfer_type_id?: number; limit?: number; offset?: number }) =>
    api.get<Transfer[]>("/inventory/transfers", { params }).then((r) => r.data),

  getTransfer: (id: number) =>
    api.get<Transfer>(`/inventory/transfers/${id}`).then((r) => r.data),

  confirmTransfer: (id: number) =>
    api.post<Transfer>(`/inventory/transfers/${id}/confirm`).then((r) => r.data),
  doneTransfer: (id: number) =>
    api.post<Transfer>(`/inventory/transfers/${id}/done`).then((r) => r.data),
  cancelTransfer: (id: number) =>
    api.post<Transfer>(`/inventory/transfers/${id}/cancel`).then((r) => r.data),
};
