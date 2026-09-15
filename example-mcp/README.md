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

เปิดใช้งาน GitHub Copilot จากนั้นสร้างไฟล์
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
