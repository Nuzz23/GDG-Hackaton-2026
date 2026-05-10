import { useState, useEffect } from 'react';
import type { DragEvent, ChangeEvent } from 'react';
import '../styles/GroupPage.css';
import { subjectApi, materialApi } from '@/services/api';
import type { Subject, Material } from '@/types/apiTypes';
import { MaterialDetailView } from '@/components/MaterialDetailView';

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

  const groupId = 1;
  const userName = "John Doe";

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
    setSelectedMaterial(null);  // close any open material when switching subjects
    setIsLoadingDetails(true);
    try {
      // Use the dedicated list endpoint — `subject.materials` from getSubject
      // is the unloaded SQLAlchemy relationship and arrives empty.
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

      <div style={{ border: "1px solid rgba(0, 0, 0, 0.1)", borderRadius: "1.2rem", margin: "0.5rem", background: "#ebebd3", display: "flex", flexDirection: "column", alignItems: "center", height: "92vh", width: "20vw", overflow: "hidden" }}>

        <div style={{ width: "100%", padding: "1rem", textAlign: "center", alignItems: "center", justifyContent: "center", fontWeight: "bold", color: "#333", fontSize: "1.2rem" }}>
          {userName}
        </div>
        <hr style={{ width: "100%", border: "none", height: "2px",margin: "0", marginBottom: "0.5rem", background: "rgba(0, 0, 0, 0.1)" }} />

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
      </div>

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
              <button style={{ width: "16rem", height: "3rem", marginRight: "1rem", borderRadius: "0.8rem", background: "rgba(152, 76, 27)", color: "white", border: "none", fontSize: "1.2rem" }} onClick={togglePopup}>
                Create new study session
              </button>
              <button style={{ width: "16rem", height: "3rem", borderRadius: "0.8rem", background: "white", color: "black", border: "1px solid #ccc", fontSize: "1.2rem" }} onClick={togglePopup}>
                Join a study session
              </button>
            </div>
          </div>
        </div>
      ) : selectedMaterial ? (
        // ─── A material is open: AI flow takes over the right pane ───
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
          />
        </div>
      ) : (
        <>
          <div style={{ border: "1px solid rgba(0, 0, 0, 0.1)", borderRadius: "1.2rem", background: "#ebebd3", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "flex-start", height: "92vh", width: "60vw", padding: "2rem", boxSizing: "border-box", overflowY: "auto" }}>
            <h1 style={{ marginBottom: "2rem", color: "#333" }}>{selectedSubject.name}</h1>

            <div style={{ width: "100%", display: "flex", flexDirection: "column", gap: "1rem" }}>
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

    </div>
  );
};