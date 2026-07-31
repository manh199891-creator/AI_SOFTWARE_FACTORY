# Sandbox Directory

`.sandbox` là DLL test lane của module.
Không phải bản sao source code.
Không commit DLL, PDB, obj, log hoặc test output.
Sandbox DLL không được promote trước khi review approved.
DLL phải được ràng buộc với source commit và SHA-256 trong manifest.json.
Không cho host load đồng thời stable manifest và sandbox manifest cùng AddInId.
