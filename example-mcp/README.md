# เชื่อม GitHub Copilot กับ Example MCP

MCP server ตัวอย่างนี้เปิดผ่าน Streamable HTTP ที่
`http://127.0.0.1:8000/mcp` และมี tool เดียวชื่อ `query` สำหรับอ่านข้อมูลจาก
PostgreSQL

เริ่ม service ก่อน:

```bash
cd example-mcp
docker compose up --build -d
docker compose ps
```

## GitHub Copilot ใน VS Code

ต้องใช้ VS Code 1.99 ขึ้นไปและเปิดใช้งาน GitHub Copilot จากนั้นสร้างไฟล์
`.vscode/mcp.json` ที่ root ของ repository:

```json
{
  "servers": {
    "greeenery-postgres": {
      "type": "http",
      "url": "http://127.0.0.1:8000/mcp"
    }
  }
}
```

หลังบันทึกไฟล์:

1. กด **Start** ที่แสดงเหนือชื่อ server ในไฟล์ `mcp.json`
2. ยืนยันว่าเชื่อถือ server นี้เมื่อ VS Code ถาม
3. เปิด Copilot Chat แล้วเลือกโหมด **Agent**
4. กด **Configure Tools** และตรวจว่ามี tool ชื่อ `query`

ลองถาม Copilot:

```text
ใช้ tool query จาก greeenery-postgres เพื่อแสดงสินค้า 5 รายการที่ราคาสูงสุด
```

หรือระบุ SQL โดยตรง:

```text
ใช้ tool query รัน SQL นี้:
select name, price from products order by price desc limit 5
```

## GitHub Copilot CLI

ถ้าใช้ Copilot CLI ให้สร้าง `.mcp.json` ที่ root ของ repository แทน ไม่ต้อง
สร้างทั้งสองไฟล์ เพราะ Copilot CLI ไม่อ่าน `.vscode/mcp.json`:

```json
{
  "mcpServers": {
    "greeenery-postgres": {
      "type": "http",
      "url": "http://127.0.0.1:8000/mcp",
      "tools": ["query"]
    }
  }
}
```

เปิด `copilot` จาก repository นี้ ยืนยันว่าเชื่อถือ workspace เมื่อระบบถาม
แล้วใช้ `/mcp list` เพื่อตรวจว่า `greeenery-postgres` พร้อมใช้งาน

## แก้ปัญหาเบื้องต้น

ถ้าไม่เห็น tool หรือเชื่อมต่อไม่ได้:

```bash
cd example-mcp
docker compose ps
docker compose logs mcp
```

- PostgreSQL ต้องมีสถานะ `healthy` และ MCP ต้องมีสถานะ `Up`
- ใน VS Code ใช้คำสั่ง **MCP: List Servers** เพื่อ start, restart หรือดู output
- ถ้า VS Code เปิดผ่าน Dev Container หรือ SSH ให้รัน Docker Compose ใน
  environment เดียวกับที่ VS Code เชื่อมต่อ เพราะ `127.0.0.1` หมายถึงเครื่อง
  นั้น

MCP endpoint ไม่มี authentication แต่ publish เฉพาะ `127.0.0.1` บัญชีฐานข้อมูล
เป็น read-only, query timeout หลัง 5 วินาที และคืนไม่เกิน 1,000 แถว

เอกสารอ้างอิง:

- [Add and manage MCP servers in VS Code](https://code.visualstudio.com/docs/agent-customization/mcp-servers)
- [Adding MCP servers for GitHub Copilot CLI](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-mcp-servers)
