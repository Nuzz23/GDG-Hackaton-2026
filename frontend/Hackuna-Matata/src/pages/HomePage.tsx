import { useState, useEffect, useMemo, useRef } from 'react';
import type { DragEvent, ChangeEvent } from 'react';
import '../styles/GroupPage.css';
import { subjectApi, materialApi, agentApi } from '@/services/api';
import type { Subject, Material, IndexOutput, HierarchyNode } from '@/types/apiTypes';
import { MaterialDetailView } from '@/components/MaterialDetailView';
import { IndexTree } from '@/components/IndexTree';
import { QuizModal } from '@/components/QuizModal';
import { findPath, nearestSectionAncestor, computeNumbering } from '@/utils/treeWalk';

type SidebarMode = 'profile' | 'index';

export const HomePage: React.FC = () => {
  const [isPopupOpen, setIsPopupOpen] = useState(false);
  const [subjectName, setSubjectName] = useState('');
  const [deadline, setDeadline] = useState('');
  const [collaborators, setCollaborators] = useState('');
  const [materials, setMaterials] = useState<File[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [subjects, setSubjects] = useState<Subject[]>([]);

  const [selectedSubject, setSelectedSubject] = useState<Subject | null>(null);
  const [subjectMaterials, setSubjectMaterials] = useState<Material[]>([]);
  const [isLoadingDetails, setIsLoadingDetails] = useState(false);
  const [selectedMaterial, setSelectedMaterial] = useState<Material | null>(null);

  // ── Document-reading state lifted up so the left sidebar can swap
  // between the John Doe profile view and the per-material Index tree.
  const [sidebarMode, setSidebarMode] = useState<SidebarMode>('profile');
  const [matIndex, setMatIndex] = useState<IndexOutput | null>(null);
  const [currentNodeId, setCurrentNodeId] = useState<string | null>(null);
  const [scrollTargetId, setScrollTargetId] = useState<string | null>(null);
  const [quizOpen, setQuizOpen] = useState(false);

  // Add-sources flow state. The hidden <input> ref is what the "+ Add sources"
  // button clicks under the hood; `addingSource` blocks repeat clicks while
  // the backend is busy indexing + merging.
  const addSourcesInputRef = useRef<HTMLInputElement>(null);
  const [addingSource, setAddingSource] = useState(false);

  const groupId = 1;
  const userName = "John Doe";

  // The node the quiz will be generated on by default — closest non-paragraph
  // ancestor of the heading currently in view. The QuizModal still lets the
  // user override the scope via its own dropdown.
  const quizTargetNode: HierarchyNode | null = useMemo(() => {
    if (!matIndex?.tree || !currentNodeId) return matIndex?.tree ?? null;
    const path = findPath(matIndex.tree, currentNodeId);
    return nearestSectionAncestor(path ?? []) ?? matIndex.tree;
  }, [matIndex, currentNodeId]);

  // Numbering map for the whole tree — passed to IndexTree so every level
  // of the recursion shares the same hierarchical numbering ("1.1.I.a").
  const numbering = useMemo(
    () => (matIndex?.tree ? computeNumbering(matIndex.tree) : new Map<string, string>()),
    [matIndex],
  );

  // Whenever we open/close a material, reset the document state and pick a
  // sensible sidebar mode (auto-flip to Index when a material is opened).
  useEffect(() => {
    setMatIndex(null);
    setCurrentNodeId(null);
    setScrollTargetId(null);
    setSidebarMode(selectedMaterial ? 'index' : 'profile');
  }, [(selectedMaterial as any)?.id]);

  const fetchSubjects = async () => {
    try {
      const response = await subjectApi.listSubjects(groupId);
      setSubjects((response as any).data || response);
    } catch (error) {
      console.error(error);
    }
  };

  useEffect(() => {
    fetchSubjects();
  }, []);

  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setSelectedSubject(null);
        setSelectedMaterial(null);
      }
    };
    window.addEventListener('keydown', handleEsc);
    return () => {
      window.removeEventListener('keydown', handleEsc);
    };
  }, []);

  const togglePopup = () => {
    setIsPopupOpen(!isPopupOpen);
    if (isPopupOpen) {
      setSubjectName('');
      setDeadline('');
      setCollaborators('');
      setMaterials([]);
    }
  };

  const handleDragOver = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
  };

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      setMaterials(Array.from(e.dataTransfer.files));
    }
  };

  const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      setMaterials(Array.from(e.target.files));
    }
  };

  const handleConfirm = async () => {
    if (!subjectName) return;

    setIsSubmitting(true);
    try {
      const subjectData = {
        name: subjectName,
        description: "",
      };

      const subjectResponse = await subjectApi.createSubject(groupId, subjectData as any);
      const newSubjectId = (subjectResponse as any).data?.id || (subjectResponse as any).id;

      if (newSubjectId && materials.length > 0) {
        const uploadPromises = materials.map(file =>
          materialApi.uploadMaterial(groupId, file, file.name, newSubjectId)
        );
        await Promise.all(uploadPromises);
      }

      await fetchSubjects();
      togglePopup();
    } catch (error) {
      console.error(error);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSubjectClick = async (subject: Subject) => {
    setSelectedSubject(subject);
    setSelectedMaterial(null);
    setIsLoadingDetails(true);
    try {
      const res = await materialApi.listBySubject(groupId, subject.id);
      const data = (res as any).data || res;
      setSubjectMaterials(Array.isArray(data) ? data : []);
    } catch (error) {
      console.error(error);
      setSubjectMaterials([]);
    } finally {
      setIsLoadingDetails(false);
    }
  };

  /** Append a new file (PDF / etc.) to the currently-open material's index.
   *  The backend processes the file and merges its tree as a new chapter at
   *  the end. We replace the local matIndex with the merged result so the
   *  sidebar tree, breadcrumb numbering and reader all update at once. */
  const handleAddSource = async (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !selectedMaterial) return;
    setAddingSource(true);
    try {
      const r = await agentApi.addSource((selectedMaterial as any).id, file);
      setMatIndex(r.data.index);
    } catch (err) {
      console.error('Add source failed', err);
    } finally {
      setAddingSource(false);
      // Allow re-selecting the same filename right away.
      if (addSourcesInputRef.current) addSourcesInputRef.current.value = '';
    }
  };

  const handleUploadNewMaterial = async (e: ChangeEvent<HTMLInputElement>) => {
    if (!selectedSubject) return;
    if (e.target.files && e.target.files.length > 0) {
      setIsLoadingDetails(true);
      try {
        const file = e.target.files[0];
        await materialApi.uploadMaterial(groupId, file, file.name, selectedSubject.id);
        await handleSubjectClick(selectedSubject);
      } catch (error) {
        console.error(error);
      } finally {
        setIsLoadingDetails(false);
      }
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "row", alignItems: "center", justifyContent: "center", position: "relative" }}>

      {/* ── Left sidebar: profile mode (John Doe + subjects) OR index mode
            (Index tree of the currently-open material). The arrow on top
            toggles between the two when a material is open. ───────────── */}
      {!(selectedMaterial && sidebarMode === 'index' && matIndex) ? (
        <div style={{ border: "1px solid rgba(0, 0, 0, 0.1)", borderRadius: "1.2rem", margin: "0.5rem", background: "#ebebd3", display: "flex", flexDirection: "column", alignItems: "center", height: "92vh", width: "20vw", overflow: "hidden" }}>

          {/* Avatar circle + truncated full name + bell/→ icon. Mirrors the
              "GF Giambattista Fer..." layout from the design mockup. */}
          <div style={{ width: "100%", padding: "1.2rem 1.2rem 0.6rem 1.2rem", display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, boxSizing: "border-box" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, minWidth: 0, flex: 1 }}>
              <div style={{
                width: 32, height: 32, borderRadius: "50%",
                background: "#3498db", color: "white", flexShrink: 0,
                display: "flex", alignItems: "center", justifyContent: "center",
                fontWeight: 700, fontSize: 12,
              }}>
                {userInitials(userName)}
              </div>
              <span style={{
                fontWeight: 700, color: "#333", fontSize: "1rem",
                whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
              }} title={userName}>
                {userName}
              </span>
            </div>
            {selectedMaterial && matIndex ? (
              <button
                onClick={() => setSidebarMode('index')}
                title="Show document index"
                style={{
                  border: "none", background: "transparent", cursor: "pointer",
                  padding: 4, display: "flex", alignItems: "center", flexShrink: 0,
                }}
              >
                <svg width="22" height="22" viewBox="0 0 24 24" fill="#333" xmlns="http://www.w3.org/2000/svg">
                  <path d="M8.59 16.59L13.17 12 8.59 7.41 10 6l6 6-6 6z"/>
                </svg>
              </button>
            ) : (
              <svg width="22" height="22" viewBox="0 0 24 24" fill="#333" xmlns="http://www.w3.org/2000/svg" style={{ cursor: "pointer", flexShrink: 0 }}>
                <path d="M12 22C13.1 22 14 21.1 14 20H10C10 21.1 10.9 22 12 22ZM18 16V11C18 7.93 16.36 5.36 13.5 4.68V4C13.5 3.17 12.83 2.5 12 2.5C11.17 2.5 10.5 3.17 10.5 4V4.68C7.63 5.36 6 7.92 6 11V16L4 18V19H20V18L18 16Z"/>
              </svg>
            )}
          </div>

          {/* Back row — appears below the user line. Shows when there's
              a context to leave (a subject browsed or a material open). */}
          {(selectedSubject || selectedMaterial) && (
            <div
              onClick={() => {
                if (selectedMaterial) setSelectedMaterial(null);
                else setSelectedSubject(null);
              }}
              style={{
                width: "100%", padding: "0.4rem 1.2rem",
                display: "flex", alignItems: "center", gap: 6,
                cursor: "pointer", color: "#333", fontSize: "0.95rem",
                fontWeight: 600, boxSizing: "border-box",
              }}
              title="Back"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="#333" xmlns="http://www.w3.org/2000/svg">
                <path d="M15.41 16.59L10.83 12l4.58-4.59L14 6l-6 6 6 6z"/>
              </svg>
              <span>{selectedMaterial ? (selectedSubject?.name ?? 'Subject') : 'Home'}</span>
            </div>
          )}

          <hr style={{ width: "100%", border: "none", height: "2px", margin: "0", marginBottom: "1rem", background: "rgba(0, 0, 0, 0.1)" }} />

          <div style={{ width: "100%", display: "flex", flexDirection: "column", alignItems: "center", gap: "0.5rem", flex: 1, overflowY: "auto", paddingBottom: "1rem" }}>
            {subjects.map((subject) => (
              <div
                key={subject.id}
                onClick={() => handleSubjectClick(subject)}
                style={{
                  width: "80%",
                  padding: "0.8rem",
                  backgroundColor: selectedSubject?.id === subject.id ? "#d4d4b8" : "white",
                  borderRadius: "0.8rem",
                  boxShadow: "0 2px 4px rgba(0,0,0,0.05)",
                  cursor: "pointer",
                  textAlign: "center",
                  fontWeight: "bold",
                  color: "#333",
                  border: "1px solid transparent",
                  transition: "all 0.2s",
                  flexShrink: 0
                }}
                onMouseEnter={(e) => { if (selectedSubject?.id !== subject.id) e.currentTarget.style.border = "1px solid #aaa" }}
                onMouseLeave={(e) => { if (selectedSubject?.id !== subject.id) e.currentTarget.style.border = "1px solid transparent" }}
              >
                {subject.name}
              </div>
            ))}
          </div>

          {/* Sticky bottom CTA — opens the same popup used by the welcome
              screen, so the user can spin up a new study session without
              having to navigate away from the current document. */}
          <div style={{
            width: "100%", padding: "0.75rem 1rem 1rem",
            borderTop: "1px solid rgba(0,0,0,0.08)", boxSizing: "border-box",
            flexShrink: 0,
          }}>
            <button
              onClick={togglePopup}
              style={{
                width: "100%", padding: "0.7rem", borderRadius: "0.7rem",
                background: "rgba(152, 76, 27)", color: "white", border: "none",
                fontSize: "0.95rem", fontWeight: 600, cursor: "pointer",
              }}
            >
              + Create new session
            </button>
          </div>
        </div>
      ) : (
        // ── Index sidebar: replaces the John Doe panel while reading. ──
        <div style={{ border: "1px solid rgba(0, 0, 0, 0.1)", borderRadius: "1.2rem", margin: "0.5rem", background: "#ebebd3", display: "flex", flexDirection: "column", height: "92vh", width: "20vw", overflow: "hidden" }}>

          {/* User header — same as the profile sidebar so the name stays
              visible while reading. The bell here is purely decorative; the
              real "back to profile" affordance is the ← arrow on the row
              below this. */}
          <div style={{ width: "100%", padding: "1.2rem 1.2rem 0.6rem 1.2rem", display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, boxSizing: "border-box" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, minWidth: 0, flex: 1 }}>
              <div style={{
                width: 32, height: 32, borderRadius: "50%",
                background: "#3498db", color: "white", flexShrink: 0,
                display: "flex", alignItems: "center", justifyContent: "center",
                fontWeight: 700, fontSize: 12,
              }}>
                {userInitials(userName)}
              </div>
              <span style={{
                fontWeight: 700, color: "#333", fontSize: "1rem",
                whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
              }} title={userName}>
                {userName}
              </span>
            </div>
            <svg width="22" height="22" viewBox="0 0 24 24" fill="#333" xmlns="http://www.w3.org/2000/svg" style={{ cursor: "pointer", flexShrink: 0 }}>
              <path d="M12 22C13.1 22 14 21.1 14 20H10C10 21.1 10.9 22 12 22ZM18 16V11C18 7.93 16.36 5.36 13.5 4.68V4C13.5 3.17 12.83 2.5 12 2.5C11.17 2.5 10.5 3.17 10.5 4V4.68C7.63 5.36 6 7.92 6 11V16L4 18V19H20V18L18 16Z"/>
            </svg>
          </div>

          {/* "Back to profile" / Index title row */}
          <div style={{ width: "100%", padding: "0.4rem 1.2rem 0.6rem", display: "flex", alignItems: "center", justifyContent: "space-between", boxSizing: "border-box" }}>
            <button
              onClick={() => setSidebarMode('profile')}
              title="Back to profile"
              style={{
                border: "none", background: "transparent", cursor: "pointer",
                padding: 4, display: "flex", alignItems: "center",
              }}
            >
              <svg width="22" height="22" viewBox="0 0 24 24" fill="#333" xmlns="http://www.w3.org/2000/svg">
                <path d="M15.41 16.59L10.83 12l4.58-4.59L14 6l-6 6 6 6z"/>
              </svg>
            </button>
            <span style={{ fontWeight: 700, color: "#333", fontSize: "1.05rem" }}>
              Index
            </span>
            <span style={{ width: 22 }} />
          </div>

          <hr style={{ width: "100%", border: "none", height: "2px", margin: "0", marginBottom: "0.5rem", background: "rgba(0, 0, 0, 0.1)" }} />

          {/* Filename header — biggest title in this column (bigger than the
              user name and the "Index" sub-title), bold + underlined. */}
          <div style={{
            padding: "0.4rem 1rem 0.8rem",
            fontSize: "1.25rem", fontWeight: 800,
            textDecoration: "underline", textUnderlineOffset: "3px",
            color: "#222", wordBreak: "break-word",
          }}>
            {matIndex.source.filename}
            <span style={{
              fontSize: "0.75rem", fontWeight: 600, color: "#789",
              textDecoration: "none", marginLeft: 6,
            }}>
              · {matIndex.source.language}
            </span>
          </div>

          <div style={{ flex: 1, overflowY: "auto", padding: "0 1rem 1rem" }}>
            <IndexTree
              node={matIndex.tree}
              selectedNodeId={currentNodeId}
              onSelect={(n) => setScrollTargetId(n.node_id)}
              numbering={numbering}
            />
          </div>

          {/* "+ Add sources" — appends a new file's index as a new chapter. */}
          <div style={{
            padding: "0.6rem 1rem 0.9rem",
            borderTop: "1px solid rgba(0,0,0,0.08)",
            flexShrink: 0,
          }}>
            <input
              ref={addSourcesInputRef}
              type="file"
              accept=".pdf,.pptx,.md,.markdown,.txt,.mp3,.wav,.m4a,.mp4,.mov"
              onChange={handleAddSource}
              style={{ display: "none" }}
            />
            <button
              onClick={() => addSourcesInputRef.current?.click()}
              disabled={addingSource}
              style={{
                width: "100%", padding: "0.7rem", borderRadius: "0.7rem",
                background: addingSource ? "rgba(152, 76, 27, 0.6)" : "rgba(152, 76, 27)",
                color: "white", border: "none",
                fontSize: "0.95rem", fontWeight: 600,
                cursor: addingSource ? "wait" : "pointer",
              }}
            >
              {addingSource ? "⏳ Adding source…" : "+ Add sources"}
            </button>
          </div>
        </div>
      )}

      {!selectedSubject ? (
        <div style={{
          border: "1px solid rgba(0, 0, 0, 0.1)",
          borderRadius: "1.2rem",
          margin: "0.5rem",
          background: "#ebebd3",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          height: "92vh",
          width: "78vw"
        }}>
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center"}}>
            <h2 style={{ fontSize: "2.5rem", fontWeight: "bold", textAlign: "left", lineHeight: "1.2", marginBottom: "0.8rem", color: "#333" }}>
              Hi {userName}!<br />
              What are we learning today?
            </h2>

            <div style={{ display: "flex", flexDirection: "row", alignItems: "center"}}>
              <button style={{ width: "16rem", height: "3rem", marginRight: "1rem", borderRadius: "0.8rem", background: "rgba(152, 76, 27)", color: "white", border: "none", fontSize: "1.2rem", cursor: "pointer" }} onClick={togglePopup}>
                Create new study session
              </button>
              <button style={{ width: "16rem", height: "3rem", borderRadius: "0.8rem", background: "white", color: "black", border: "1px solid #ccc", fontSize: "1.2rem", cursor: "pointer" }} onClick={togglePopup}>
                Join a study session
              </button>
            </div>
          </div>
        </div>
      ) : selectedMaterial ? (
        <div style={{
          border: "1px solid rgba(0, 0, 0, 0.1)",
          borderRadius: "1.2rem",
          margin: "0.5rem",
          background: "#ebebd3",
          height: "92vh",
          width: "78vw",
          boxSizing: "border-box",
        }}>
          <MaterialDetailView
            groupId={groupId}
            materialId={(selectedMaterial as any).id}
            materialName={(selectedMaterial as any).name || 'Document'}
            onBack={() => setSelectedMaterial(null)}
            index={matIndex}
            onIndexLoaded={setMatIndex}
            currentNodeId={currentNodeId}
            onCurrentNodeChange={setCurrentNodeId}
            scrollTargetId={scrollTargetId}
            onOpenQuiz={() => setQuizOpen(true)}
            canOpenQuiz={!!quizTargetNode}
          />
        </div>
      ) : (
        <>
          <div style={{ border: "1px solid rgba(0, 0, 0, 0.1)", borderRadius: "1.2rem", background: "#ebebd3", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "flex-start", height: "92vh", width: "60vw",  boxSizing: "border-box", overflowY: "auto", margin: "0.5rem" }}>
            <h1 style={{ marginBottom: "2rem", color: "#333" }}>{selectedSubject.name}</h1>

            <div style={{ width: "100%", display: "flex", flexDirection: "column", gap: "1rem", padding: "0 1rem", boxSizing: "border-box" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <h3 style={{ margin: 0, color: "#555" }}>Materials</h3>
                <div>
                  <input
                    id="inner-file-upload"
                    type="file"
                    onChange={handleUploadNewMaterial}
                    style={{ display: "none" }}
                  />
                  <button
                    onClick={() => document.getElementById('inner-file-upload')?.click()}
                    style={{ padding: "0.5rem 1rem", cursor: "pointer" }}
                  >
                    Upload Material
                  </button>
                </div>
              </div>

              {isLoadingDetails ? (
                <p>Loading materials...</p>
              ) : subjectMaterials.length > 0 ? (
                subjectMaterials.map((material, index) => (
                  <div
                    key={(material as any).id || index}
                    onClick={() => setSelectedMaterial(material)}
                    style={{
                      padding: "1rem",
                      margin: "0 1rem",
                      backgroundColor: "white",
                      borderRadius: "0.8rem",
                      boxShadow: "0 2px 4px rgba(0,0,0,0.05)",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      cursor: "pointer",
                      transition: "transform 0.1s",
                    }}
                    onMouseEnter={(e) => { e.currentTarget.style.transform = "translateX(4px)"; }}
                    onMouseLeave={(e) => { e.currentTarget.style.transform = "translateX(0)"; }}
                  >
                    <span style={{ fontWeight: "bold", color: "#444" }}>
                      📄 {(material as any).name || 'Document'}
                    </span>
                    <span style={{ fontSize: "0.85rem", color: "#888" }}>
                      Open AI flow →
                    </span>
                  </div>
                ))
              ) : (
                <p style={{ color: "#777", fontStyle: "italic" }}>No materials found for this subject.</p>
              )}
            </div>
          </div>

          <div style={{ border: "1px solid rgba(0, 0, 0, 0.1)", borderRadius: "1.2rem", margin: "0.5rem", background: "#ebebd3", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", height: "92vh", width: "20vw" }}>
          </div>
        </>
      )}
      

      {isPopupOpen && (
        <div style={{
          position: "fixed",
          top: 0,
          left: 0,
          width: "100vw",
          height: "100vh",
          backgroundColor: "rgba(0, 0, 0, 0.5)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          zIndex: 1000
        }}>

          <div style={{
            background: "white",
            padding: "2rem",
            borderRadius: "1.2rem",
            boxShadow: "0 4px 6px rgba(0, 0, 0, 0.1)",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            width: "50vw",
            height: "auto",
            gap: "1rem"
          }}>
            <h2>New Study Session</h2>

            <input
              type="text"
              placeholder="Subject Name"
              value={subjectName}
              onChange={(e) => setSubjectName(e.target.value)}
              style={{ width: "80%", padding: "0.5rem", borderRadius: "0.5rem", border: "1px solid #ccc" }}
            />

            <input
              type="date"
              value={deadline}
              onChange={(e) => setDeadline(e.target.value)}
              style={{ width: "80%", padding: "0.5rem", borderRadius: "0.5rem", border: "1px solid #ccc" }}
            />

            <input
              type="text"
              placeholder="Invite Collaborators"
              value={collaborators}
              onChange={(e) => setCollaborators(e.target.value)}
              style={{ width: "80%", padding: "0.5rem", borderRadius: "0.5rem", border: "1px solid #ccc" }}
            />

            <div
              onDragOver={handleDragOver}
              onDrop={handleDrop}
              onClick={() => document.getElementById('popup-file-upload')?.click()}
              style={{
                width: "80%",
                height: "150px",
                border: "2px dashed #ccc",
                borderRadius: "0.5rem",
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                cursor: "pointer",
                backgroundColor: "#f9f9f9"
              }}
            >
              <p>Drag and drop materials here, or click to select</p>
              <input
                id="popup-file-upload"
                type="file"
                multiple
                onChange={handleFileChange}
                style={{ display: "none" }}
              />
              {materials.length > 0 && (
                <div style={{ marginTop: "0.5rem", fontSize: "0.8rem", textAlign: "center", maxHeight: "60px", overflowY: "auto" }}>
                  {materials.map((m, i) => (
                    <div key={i}>{m.name}</div>
                  ))}
                </div>
              )}
            </div>

            <div style={{ display: "flex", gap: "1rem", marginTop: "1.5rem" }}>
              <button onClick={togglePopup} disabled={isSubmitting} style={{ padding: "0.5rem 1rem", cursor: "pointer" }}>
                Cancel
              </button>
              <button onClick={handleConfirm} disabled={isSubmitting || !subjectName} style={{ padding: "0.5rem 1rem", cursor: "pointer" }}>
                {isSubmitting ? "Confirming..." : "Confirm"}
              </button>
            </div>
          </div>

        </div>
      )}

      {/* Quiz modal — lifted up here so the trigger can live in the
          Index sidebar (left column) while the modal still overlays the
          whole window. */}
      <QuizModal
        isOpen={quizOpen}
        onClose={() => setQuizOpen(false)}
        materialId={(selectedMaterial as any)?.id ?? 0}
        tree={matIndex?.tree ?? null}
        targetNode={quizTargetNode}
      />

    </div>
  );
};

/** "John Doe" → "JD". Falls back to the first 2 chars on single-token names. */
function userInitials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return '?';
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}