/** i18next setup with Thai + English. */
import i18n from "i18next";
import LanguageDetector from "i18next-browser-languagedetector";
import { initReactI18next } from "react-i18next";

const TH = {
  // Navigation
  "nav.home": "หน้าหลัก",
  "nav.products": "สินค้า",
  "nav.warehouses": "คลังสินค้า",
  "nav.transfers": "การโอน",
  "nav.outbound": "การส่งสินค้า",
  "nav.couriers": "ขนส่ง",
  "nav.counts": "ตรวจนับ",
  "nav.quality": "คุณภาพ",
  "nav.ops": "ปฏิบัติการ",
  "nav.purchase": "จัดซื้อ",
  "nav.manufacturing": "ผลิต",
  "nav.sales": "ขาย",
  "nav.accounting": "บัญชี",
  "nav.hr": "ทรัพยากรบุคคล",
  "nav.audit": "บันทึกตรวจสอบ",
  "nav.users": "ผู้ใช้งาน",

  // Common actions
  "action.create": "สร้างใหม่",
  "action.save": "บันทึก",
  "action.discard": "ยกเลิก",
  "action.edit": "แก้ไข",
  "action.delete": "ลบ",
  "action.archive": "เก็บถาวร",
  "action.unarchive": "เลิกเก็บถาวร",
  "action.search": "ค้นหา",
  "action.signOut": "ออกจากระบบ",
  "action.signIn": "เข้าสู่ระบบ",
  "action.confirm": "ยืนยัน",
  "action.cancel": "ยกเลิก",
  "action.close": "ปิด",
  "action.refresh": "รีเฟรช",

  // Status
  "status.active": "ใช้งาน",
  "status.archived": "เก็บถาวร",
  "status.loading": "กำลังโหลด...",
  "status.empty": "ยังไม่มีข้อมูล",
  "status.error": "เกิดข้อผิดพลาด",
  "status.saved": "บันทึกแล้ว",

  // Filters
  "filter.all": "ทั้งหมด",
  "filter.active": "ใช้งานอยู่",
  "filter.archived": "เก็บถาวร",
  "filter.superusers": "ผู้ดูแลระบบ",

  // View modes
  "view.list": "รายการ",
  "view.form": "ฟอร์ม",
  "view.kanban": "การ์ด",
  "view.search": "ค้นหา",
  "view.gridDensity": "ความหนาแน่น",

  // Users module
  "users.title": "ผู้ใช้งาน",
  "users.subtitle": "จัดการผู้ใช้ บทบาท บริษัท และภาษา",
  "users.newUser": "ผู้ใช้ใหม่",
  "users.email": "อีเมล",
  "users.fullName": "ชื่อ-นามสกุล",
  "users.password": "รหัสผ่าน",
  "users.lastLogin": "เข้าใช้ครั้งล่าสุด",
  "users.companies": "บริษัท",
  "users.defaultCompany": "บริษัทเริ่มต้น",
  "users.locale": "ภาษา",
  "users.groups": "กลุ่มสิทธิ์",
  "users.isSuperuser": "ผู้ดูแลระบบ",
  "users.isActive": "เปิดใช้งาน",

  // Sections
  "section.identity": "ข้อมูลทั่วไป",
  "section.access": "การเข้าถึง",
  "section.preferences": "การตั้งค่า",
  "section.audit": "ประวัติการใช้งาน",

  // Currency / Date
  "currency.thb": "บาท",
  "date.never": "ไม่เคย",

  // Categories on home launcher
  "category.core": "ผู้ดูแล",
  "category.wms": "คลังสินค้า",
  "category.ops": "ปฏิบัติการ",
  "category.finance": "การเงิน",
  "category.people": "บุคคล",

  // Home / launcher
  "home.greeting.morning": "สวัสดีตอนเช้า",
  "home.greeting.afternoon": "สวัสดีตอนบ่าย",
  "home.greeting.evening": "สวัสดีตอนเย็น",
  "home.subtitle": "เลือกแอปพลิเคชันที่ต้องการเริ่ม",
  "home.searchApps": "ค้นหาแอป...",
  "home.theme.light": "สว่าง",
  "home.theme.dark": "มืด",
  "home.density.compact": "กะทัดรัด",
  "home.density.comfy": "สบายตา",
  "home.allApps": "ทุกแอป",
  "home.noResults": "ไม่พบแอปที่ค้นหา",
  "home.comingSoon": "เร็ว ๆ นี้",
};

const EN = {
  "nav.home": "Home",
  "nav.products": "Products",
  "nav.warehouses": "Warehouses",
  "nav.transfers": "Transfers",
  "nav.outbound": "Outbound",
  "nav.couriers": "Couriers",
  "nav.counts": "Counts",
  "nav.quality": "Quality",
  "nav.ops": "Operations",
  "nav.purchase": "Purchase",
  "nav.manufacturing": "Manufacturing",
  "nav.sales": "Sales",
  "nav.accounting": "Accounting",
  "nav.hr": "HR",
  "nav.audit": "Audit Log",
  "nav.users": "Users",

  "action.create": "Create",
  "action.save": "Save",
  "action.discard": "Discard",
  "action.edit": "Edit",
  "action.delete": "Delete",
  "action.archive": "Archive",
  "action.unarchive": "Unarchive",
  "action.search": "Search",
  "action.signOut": "Sign out",
  "action.signIn": "Sign in",
  "action.confirm": "Confirm",
  "action.cancel": "Cancel",
  "action.close": "Close",
  "action.refresh": "Refresh",

  "status.active": "Active",
  "status.archived": "Archived",
  "status.loading": "Loading…",
  "status.empty": "No records yet",
  "status.error": "Something went wrong",
  "status.saved": "Saved",

  "filter.all": "All",
  "filter.active": "Active",
  "filter.archived": "Archived",
  "filter.superusers": "Superusers",

  "view.list": "List",
  "view.form": "Form",
  "view.kanban": "Kanban",
  "view.search": "Search",
  "view.gridDensity": "Density",

  "users.title": "Users",
  "users.subtitle": "Manage users, roles, companies, and language",
  "users.newUser": "New user",
  "users.email": "Email",
  "users.fullName": "Full name",
  "users.password": "Password",
  "users.lastLogin": "Last login",
  "users.companies": "Companies",
  "users.defaultCompany": "Default company",
  "users.locale": "Language",
  "users.groups": "Groups",
  "users.isSuperuser": "Superuser",
  "users.isActive": "Active",

  "section.identity": "Identity",
  "section.access": "Access",
  "section.preferences": "Preferences",
  "section.audit": "Activity",

  "currency.thb": "THB",
  "date.never": "Never",

  "category.core": "Admin",
  "category.wms": "Warehouse",
  "category.ops": "Operations",
  "category.finance": "Finance",
  "category.people": "People",

  "home.greeting.morning": "Good morning",
  "home.greeting.afternoon": "Good afternoon",
  "home.greeting.evening": "Good evening",
  "home.subtitle": "Pick an app to dive in",
  "home.searchApps": "Search apps...",
  "home.theme.light": "Light",
  "home.theme.dark": "Dark",
  "home.density.compact": "Compact",
  "home.density.comfy": "Comfy",
  "home.allApps": "All apps",
  "home.noResults": "No matching apps",
  "home.comingSoon": "Coming soon",
};

void i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: {
      th: { translation: TH },
      en: { translation: EN },
    },
    fallbackLng: "th",
    interpolation: { escapeValue: false },
    detection: {
      order: ["localStorage", "navigator"],
      caches: ["localStorage"],
      lookupLocalStorage: "kob.locale",
    },
  });

export default i18n;
