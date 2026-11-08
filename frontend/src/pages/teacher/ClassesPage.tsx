import { useCallback, useEffect, useState } from "react";
import { Archive, FileSpreadsheet, Pencil, Plus, Search, Upload, UserPlus } from "lucide-react";
import {
  rosterApi,
  type ClassroomDTO,
  type ImportPreviewResponse,
  type StudentDTO,
} from "../../api/client";
import { StatusBadge } from "../../components/StatusBadge";

export function ClassesPage() {
  const [classes, setClasses] = useState<ClassroomDTO[]>([]);
  const [selectedClassId, setSelectedClassId] = useState<string>("");
  const [students, setStudents] = useState<StudentDTO[]>([]);
  const [searchTerm, setSearchTerm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  // Create class
  const [newClassName, setNewClassName] = useState("");
  const [newYear, setNewYear] = useState("2026-2027");

  // Add student
  const [newCode, setNewCode] = useState("");
  const [newName, setNewName] = useState("");

  // Edit student
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingName, setEditingName] = useState("");

  // Import CSV/XLSX dry-run
  const [previewData, setPreviewData] = useState<ImportPreviewResponse | null>(null);
  const [duplicatePolicy, setDuplicatePolicy] = useState<"skip" | "update_name">("skip");
  const [importing, setImporting] = useState(false);

  const loadClasses = useCallback(async () => {
    try {
      const list = await rosterApi.listClasses();
      setClasses(list);
      if (list.length > 0 && !selectedClassId) {
        setSelectedClassId(list[0]?.id ?? "");
      }
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không tải được danh sách lớp.");
    }
  }, [selectedClassId]);

  const loadStudents = useCallback(async (classId: string) => {
    if (!classId) {
      setStudents([]);
      return;
    }
    try {
      const rows = await rosterApi.listStudents(classId);
      setStudents(rows);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không tải được danh sách học sinh.");
    }
  }, []);

  useEffect(() => {
    void loadClasses();
  }, [loadClasses]);

  useEffect(() => {
    void loadStudents(selectedClassId);
  }, [selectedClassId, loadStudents]);

  const handleCreateClass = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newClassName.trim()) return;
    try {
      const created = await rosterApi.createClass(newClassName.trim(), newYear.trim());
      setNewClassName("");
      setNotice(`Đã tạo lớp ${created.name}.`);
      await loadClasses();
      setSelectedClassId(created.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không tạo được lớp.");
    }
  };

  const handleAddStudent = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedClassId || !newCode.trim() || !newName.trim()) return;
    try {
      await rosterApi.createStudent(selectedClassId, newCode.trim(), newName.trim());
      setNewCode("");
      setNewName("");
      setNotice("Đã thêm học sinh.");
      await loadStudents(selectedClassId);
      await loadClasses();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không thêm được học sinh.");
    }
  };

  const handleSaveEdit = async (studentId: string) => {
    if (!editingName.trim()) return;
    try {
      await rosterApi.updateStudent(studentId, editingName.trim());
      setEditingId(null);
      setNotice("Đã cập nhật họ tên (giữ nguyên mã và lịch sử điểm).");
      await loadStudents(selectedClassId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không cập nhật được họ tên.");
    }
  };

  const handleArchiveStudent = async (st: StudentDTO) => {
    if (!window.confirm(`Lưu trữ học sinh ${st.full_name} (${st.roster_code})? Lịch sử điểm cũ vẫn được giữ nguyên.`)) {
      return;
    }
    try {
      await rosterApi.archiveStudent(st.id);
      setNotice(`Đã lưu trữ ${st.roster_code}.`);
      await loadStudents(selectedClassId);
      await loadClasses();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không thể lưu trữ học sinh.");
    }
  };

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !selectedClassId) return;
    try {
      setImporting(true);
      const preview = await rosterApi.previewImport(selectedClassId, file);
      setPreviewData(preview);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không đọc được file danh sách.");
      setPreviewData(null);
    } finally {
      setImporting(false);
      e.target.value = "";
    }
  };

  const handleCommitImport = async () => {
    if (!previewData || !selectedClassId) return;
    try {
      setImporting(true);
      const summary = await rosterApi.commitImport(selectedClassId, previewData.rows, duplicatePolicy);
      setPreviewData(null);
      setNotice(
        `Đã nhập danh sách: Thêm mới ${summary.added}, Cập nhật tên ${summary.updated}, Bỏ qua ${summary.skipped}.`
      );
      await loadStudents(selectedClassId);
      await loadClasses();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Lỗi khi xác nhận nhập danh sách.");
    } finally {
      setImporting(false);
    }
  };

  const filteredStudents = students.filter(
    (s) =>
      s.roster_code.toLowerCase().includes(searchTerm.toLowerCase()) ||
      s.full_name.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">
          Quản lý lớp học & danh sách học sinh
        </h1>
        <p className="mt-1 text-sm text-slate-600">
          Nhập danh sách từ Excel/CSV một lần và dùng cho cả năm học. Mã học sinh là định danh cố định.
        </p>
      </div>

      {error ? (
        <div role="alert" className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800">
          {error}
        </div>
      ) : null}
      {notice ? (
        <div role="status" className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800">
          {notice}
        </div>
      ) : null}

      <div className="grid gap-6 lg:grid-cols-4">
        {/* Class list sidebar */}
        <section className="rounded-xl border border-slate-200 bg-white p-4 lg:col-span-1">
          <h2 className="text-sm font-semibold text-slate-900">Danh sách lớp</h2>
          <form onSubmit={handleCreateClass} className="mt-3 space-y-2">
            <input
              type="text"
              placeholder="Tên lớp (vd: 12A1)"
              value={newClassName}
              onChange={(e) => setNewClassName(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-1.5 text-sm"
            />
            <input
              type="text"
              placeholder="Năm học"
              value={newYear}
              onChange={(e) => setNewYear(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-1.5 text-sm"
            />
            <button
              type="submit"
              className="inline-flex w-full items-center justify-center gap-1.5 rounded-lg bg-[#1E3A5F] px-3 py-2 text-xs font-semibold text-white hover:bg-[#162C49]"
            >
              <Plus className="h-3.5 w-3.5" aria-hidden="true" />
              <span>Thêm lớp mới</span>
            </button>
          </form>

          <ul className="mt-4 space-y-1.5">
            {classes.map((cls) => (
              <li key={cls.id}>
                <button
                  type="button"
                  onClick={() => setSelectedClassId(cls.id)}
                  className={`flex w-full items-center justify-between rounded-lg px-3 py-2 text-left text-sm ${
                    selectedClassId === cls.id
                      ? "bg-[#1E3A5F] font-semibold text-white"
                      : "bg-slate-50 text-slate-700 hover:bg-slate-100"
                  }`}
                >
                  <span>{cls.name}</span>
                  <span className="font-mono-data text-xs opacity-80">{cls.student_count} HS</span>
                </button>
              </li>
            ))}
            {classes.length === 0 ? (
              <li className="text-xs text-slate-500">Chưa có lớp học nào.</li>
            ) : null}
          </ul>
        </section>

        {/* Student table + Import */}
        <section className="space-y-4 rounded-xl border border-slate-200 bg-white p-5 lg:col-span-3">
          {!selectedClassId ? (
            <p className="text-sm text-slate-500">Hãy tạo hoặc chọn một lớp học ở cột bên trái.</p>
          ) : (
            <>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="relative flex-1 min-w-[200px]">
                  <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" aria-hidden="true" />
                  <input
                    type="search"
                    placeholder="Tìm theo mã học sinh hoặc họ tên..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    className="w-full rounded-lg border border-slate-300 py-2 pl-9 pr-3 text-sm"
                  />
                </div>

                <label className="inline-flex cursor-pointer items-center gap-2 rounded-lg border border-[#0F766E] bg-emerald-50 px-3.5 py-2 text-xs font-semibold text-[#0F766E] hover:bg-emerald-100">
                  <FileSpreadsheet className="h-4 w-4" aria-hidden="true" />
                  <span>{importing ? "Đang đọc file..." : "Nhập Excel / CSV"}</span>
                  <input
                    type="file"
                    accept=".csv,.xlsx"
                    onChange={handleFileSelect}
                    className="sr-only"
                  />
                </label>
              </div>

              {/* Dry-run import preview */}
              {previewData ? (
                <div className="rounded-lg border border-sky-200 bg-sky-50 p-4 space-y-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <h3 className="text-sm font-semibold text-slate-900">
                      Xem trước kết quả kiểm tra file (Dry-run)
                    </h3>
                    <div className="flex flex-wrap gap-2">
                      <StatusBadge tone="success" label={`Mới: ${previewData.new_count}`} />
                      <StatusBadge tone="warning" label={`Trùng: ${previewData.conflict_count}`} />
                      <StatusBadge tone="danger" label={`Lỗi: ${previewData.invalid_count}`} />
                    </div>
                  </div>

                  {previewData.has_conflicts ? (
                    <div className="flex flex-wrap items-center gap-3 text-xs text-slate-800">
                      <span className="font-medium">Cách xử lý mã đã tồn tại:</span>
                      <label className="inline-flex items-center gap-1">
                        <input
                          type="radio"
                          checked={duplicatePolicy === "skip"}
                          onChange={() => setDuplicatePolicy("skip")}
                        />
                        Bỏ qua dòng trùng
                      </label>
                      <label className="inline-flex items-center gap-1">
                        <input
                          type="radio"
                          checked={duplicatePolicy === "update_name"}
                          onChange={() => setDuplicatePolicy("update_name")}
                        />
                        Cập nhật họ tên (giữ nguyên ID)
                      </label>
                    </div>
                  ) : null}

                  <div className="max-h-52 overflow-y-auto rounded border border-slate-200 bg-white">
                    <table className="w-full text-left text-xs">
                      <thead className="border-b border-slate-200 bg-slate-50 text-slate-500">
                        <tr>
                          <th className="p-2">Dòng</th>
                          <th className="p-2">Mã HS</th>
                          <th className="p-2">Họ tên</th>
                          <th className="p-2">Trạng thái</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100">
                        {previewData.rows.map((r) => (
                          <tr key={`${r.row_number}-${r.roster_code}`}>
                            <td className="p-2 font-mono-data">{r.row_number}</td>
                            <td className="p-2 font-mono-data font-medium">{r.roster_code}</td>
                            <td className="p-2">{r.full_name}</td>
                            <td className="p-2 text-slate-600">{r.message}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>

                  <div className="flex justify-end gap-2">
                    <button
                      type="button"
                      onClick={() => setPreviewData(null)}
                      className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700"
                    >
                      Hủy bỏ
                    </button>
                    <button
                      type="button"
                      onClick={handleCommitImport}
                      className="inline-flex items-center gap-1.5 rounded-lg bg-[#1E3A5F] px-3.5 py-1.5 text-xs font-semibold text-white"
                    >
                      <Upload className="h-3.5 w-3.5" aria-hidden="true" />
                      <span>Xác nhận nhập vào lớp</span>
                    </button>
                  </div>
                </div>
              ) : null}

              {/* Add single student */}
              <form onSubmit={handleAddStudent} className="flex flex-wrap gap-2 rounded-lg bg-slate-50 p-3">
                <input
                  type="text"
                  placeholder="Mã HS (vd: HS001)"
                  value={newCode}
                  onChange={(e) => setNewCode(e.target.value)}
                  className="font-mono-data w-36 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm"
                />
                <input
                  type="text"
                  placeholder="Họ và tên học sinh"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  className="min-w-[200px] flex-1 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm"
                />
                <button
                  type="submit"
                  className="inline-flex items-center gap-1.5 rounded-lg bg-[#0F766E] px-3.5 py-1.5 text-xs font-semibold text-white hover:bg-[#0D655E]"
                >
                  <UserPlus className="h-3.5 w-3.5" aria-hidden="true" />
                  <span>Thêm học sinh</span>
                </button>
              </form>

              {/* Roster table */}
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead>
                    <tr className="border-b border-slate-200 text-xs uppercase text-slate-500">
                      <th className="py-2 pr-4">Mã học sinh</th>
                      <th className="py-2 pr-4">Họ và tên</th>
                      <th className="py-2 text-right">Thao tác</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {filteredStudents.map((st) => (
                      <tr key={st.id}>
                        <td className="font-mono-data py-2.5 pr-4 font-medium text-slate-900">
                          {st.roster_code}
                        </td>
                        <td className="py-2.5 pr-4">
                          {editingId === st.id ? (
                            <div className="flex items-center gap-2">
                              <input
                                type="text"
                                value={editingName}
                                onChange={(e) => setEditingName(e.target.value)}
                                className="rounded border border-slate-300 px-2 py-1 text-sm"
                              />
                              <button
                                type="button"
                                onClick={() => void handleSaveEdit(st.id)}
                                className="rounded bg-[#1E3A5F] px-2.5 py-1 text-xs font-medium text-white"
                              >
                                Lưu
                              </button>
                              <button
                                type="button"
                                onClick={() => setEditingId(null)}
                                className="text-xs text-slate-500"
                              >
                                Hủy
                              </button>
                            </div>
                          ) : (
                            <span className="text-slate-900">{st.full_name}</span>
                          )}
                        </td>
                        <td className="py-2.5 text-right">
                          <div className="inline-flex items-center gap-2">
                            <button
                              type="button"
                              onClick={() => {
                                setEditingId(st.id);
                                setEditingName(st.full_name);
                              }}
                              className="inline-flex items-center gap-1 rounded border border-slate-300 px-2 py-1 text-xs text-slate-700 hover:bg-slate-50"
                            >
                              <Pencil className="h-3 w-3" aria-hidden="true" />
                              <span>Sửa tên</span>
                            </button>
                            <button
                              type="button"
                              onClick={() => void handleArchiveStudent(st)}
                              className="inline-flex items-center gap-1 rounded border border-red-200 px-2 py-1 text-xs text-red-700 hover:bg-red-50"
                            >
                              <Archive className="h-3 w-3" aria-hidden="true" />
                              <span>Lưu trữ</span>
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                    {filteredStudents.length === 0 ? (
                      <tr>
                        <td colSpan={3} className="py-6 text-center text-sm text-slate-500">
                          Chưa có học sinh phù hợp trong lớp này.
                        </td>
                      </tr>
                    ) : null}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </section>
      </div>
    </div>
  );
}
