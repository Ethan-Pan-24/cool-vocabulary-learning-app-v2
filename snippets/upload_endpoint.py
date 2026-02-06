@router.post("/upload_media")
async def upload_media(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    if not file or not file.filename:
        return {"status": "error", "msg": "No file uploaded"}
        
    safe_filename = "".join(c for c in file.filename if c.isalnum() or c in "._- ")
    filename = f"upload_{safe_filename}"
    
    if not os.path.exists("static/images"):
        os.makedirs("static/images")
        
    filepath = os.path.join("static/images", filename)
    
    # Avoid overwrite collision slightly or just overwrite? 
    # Let's simple overwrite for now or timestamp it? 
    # Timestamp is safer.
    import time
    filename = f"{int(time.time())}_{safe_filename}"
    filepath = os.path.join("static/images", filename)

    with open(filepath, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    url = f"/static/images/{filename}"
    return {"status": "success", "url": url}
