import { Routes, Route } from "react-router-dom";
import Layout from "./components/Layout";
import Dashboard from "./pages/Dashboard";
import Search from "./pages/Search";
import Browse from "./pages/Browse";
import NoteView from "./pages/NoteView";
import Settings from "./pages/Settings";
import Connections from "./pages/Connections";
import EntityPage from "./pages/EntityPage";
import ConceptPage from "./pages/ConceptPage";
import Capture from "./pages/Capture";

export default function App() {
  return (
    <Routes>
      {/* Mobile-friendly capture (standalone, no sidebar) */}
      <Route path="/capture" element={<Capture />} />

      {/* Main app with sidebar layout */}
      <Route element={<Layout />}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/search" element={<Search />} />
        <Route path="/browse" element={<Browse />} />
        <Route path="/notes/:noteId" element={<NoteView />} />
        <Route path="/connections" element={<Connections />} />
        <Route path="/entities/:entityId" element={<EntityPage />} />
        <Route path="/concepts/:conceptId" element={<ConceptPage />} />
        <Route path="/settings" element={<Settings />} />
      </Route>
    </Routes>
  );
}
