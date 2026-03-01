import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent } from "@/components/ui/card";
import { Download } from "lucide-react";

interface FinalBundleProps {
  scenes: Record<string, { id: string, title?: string, text: string, imageUrl?: string, audioUrl?: string }>;
  topic: string;
}

export default function FinalBundle({ scenes, topic }: FinalBundleProps) {
  const sceneList = Object.values(scenes);
  
  if (sceneList.length === 0) return null;

  const fullTranscript = sceneList.map((s, i) => `Scene ${i + 1}: ${s.title || ''}\n\n${s.text}`).join('\\n\\n---\\n\\n');

  const handleDownloadTranscript = () => {
    const blob = new Blob([fullTranscript], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `explainflow-transcript-${topic.replace(/\s+/g, '-').toLowerCase() || 'export'}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <div className="flex justify-center mt-12 mb-8">
      <Sheet>
        <SheetTrigger asChild>
          <Button size="lg" className="bg-green-600 hover:bg-green-700 text-white font-semibold px-8 py-6 rounded-full shadow-lg transition-transform hover:scale-105">
            <Download className="mr-2 h-5 w-5" />
            Export Final Bundle
          </Button>
        </SheetTrigger>
        <SheetContent side="right" className="w-full sm:max-w-2xl bg-slate-50">
          <SheetHeader className="pb-6 border-b border-slate-200">
            <SheetTitle className="text-3xl font-bold text-slate-900">Final Explainer Bundle</SheetTitle>
            <SheetDescription className="text-base">
              Review and export your generated assets for <span className="font-semibold text-slate-700">{topic || 'your project'}</span>.
            </SheetDescription>
          </SheetHeader>
          
          <Tabs defaultValue="transcript" className="mt-6">
            <TabsList className="grid w-full grid-cols-2">
              <TabsTrigger value="transcript">Full Transcript</TabsTrigger>
              <TabsTrigger value="manifest">Asset Manifest</TabsTrigger>
            </TabsList>
            
            <TabsContent value="transcript" className="mt-4">
              <Card className="border-slate-200 shadow-sm">
                <CardContent className="p-0">
                  <div className="bg-slate-900 flex justify-between items-center px-4 py-3 rounded-t-lg">
                    <span className="text-sm font-medium text-slate-200">transcript.txt</span>
                    <Button variant="secondary" size="sm" onClick={handleDownloadTranscript}>
                      <Download className="mr-2 h-4 w-4" /> Download
                    </Button>
                  </div>
                  <ScrollArea className="h-[60vh] w-full rounded-b-lg border-t-0 border bg-white p-6">
                    <pre className="text-sm font-sans whitespace-pre-wrap leading-relaxed text-slate-800">
                      {fullTranscript}
                    </pre>
                  </ScrollArea>
                </CardContent>
              </Card>
            </TabsContent>
            
            <TabsContent value="manifest" className="mt-4">
              <ScrollArea className="h-[60vh] w-full pr-4">
                <div className="space-y-6">
                  {sceneList.map((scene, i) => (
                    <div key={scene.id} className="bg-white p-4 rounded-lg border border-slate-200 shadow-sm">
                      <h4 className="font-semibold text-slate-900 mb-3">Scene {i + 1}: {scene.title}</h4>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {scene.imageUrl && (
                          <div className="flex flex-col gap-2">
                            <span className="text-xs font-medium text-slate-500 uppercase tracking-wider">Visual Asset</span>
                            <img src={scene.imageUrl} alt={`Scene ${i + 1}`} className="rounded-md w-full object-cover aspect-video border border-slate-100" />
                            <a href={scene.imageUrl} target="_blank" rel="noreferrer" className="text-sm text-blue-600 hover:underline flex items-center">
                              Open Original <Download className="ml-1 h-3 w-3" />
                            </a>
                          </div>
                        )}
                        {scene.audioUrl && (
                          <div className="flex flex-col gap-2 justify-center">
                            <span className="text-xs font-medium text-slate-500 uppercase tracking-wider">Voiceover Asset</span>
                            <audio controls src={scene.audioUrl} className="w-full h-10" />
                            <a href={scene.audioUrl} download className="text-sm text-blue-600 hover:underline flex items-center">
                              Download MP3 <Download className="ml-1 h-3 w-3" />
                            </a>
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </ScrollArea>
            </TabsContent>
          </Tabs>
        </SheetContent>
      </Sheet>
    </div>
  );
}
