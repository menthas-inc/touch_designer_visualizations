"""Record the mapper output, what the projector sees, to a Motion JPEG .mov for MINUTES minutes.

    exec(open('~/dev/studio_visuals/td/record.py').read())

Writes TD_Mapping/Recordings/studio_<date>.mov and stops on its own. H.264 needs a commercial
licence, so the file is big; shrink it after with
    ffmpeg -i studio_<date>.mov -c:v libx264 -crf 20 -pix_fmt yuv420p studio_<date>.mp4
To stop early:
    op('/project1/rec').par.record = 0; op('/project1/rec_cook').par.active = 0
Running it again while a recording is on restarts the ten minutes into a new file. A Movie
File Out only writes the frames it cooks and nothing pulls this one, so rec_cook cooks it
every frame while the recording runs.
"""
import datetime
import os

MINUTES = 5
_proj = op("/project1")
_rec = _proj.op("rec") or _proj.create(moviefileoutTOP, "rec")
_tmr = _proj.op("rec_timer") or _proj.create(timerCHOP, "rec_timer")
_rec.par.record = 0
_rec.inputConnectors[0].connect(_proj.op("kantanMapper1/out1").outputConnectors[0])
_out = os.path.join(project.folder, "Recordings")
os.makedirs(_out, exist_ok=True)
_rec.par.file = os.path.join(_out, "studio_" + datetime.datetime.now().strftime("%Y%m%d_%H%M") + ".mov")
_rec.par.videocodec = "mjpa"  # Motion JPEG A, the free edition writes it
_rec.par.qualityscale = 0.85
_ck = _proj.op("rec_cook") or _proj.create(executeDAT, "rec_cook")
_ck.par.framestart = True
_ck.text = "def onFrameStart(frame):\n    op('/project1/rec').cook()\n    return\n"
_tmr.par.lengthunits = "seconds"
_tmr.par.length = MINUTES * 60
_tmr.par.callbacks = "rec_timer_cb"
_cb = _proj.op("rec_timer_cb") or _proj.create(textDAT, "rec_timer_cb")
_cb.text = ("def onDone(timerOp, segment, interrupt):\n    op('/project1/rec').par.record = 0\n"
            "    op('/project1/rec_cook').par.active = 0\n    print('recording done')\n    return\n")
_rec.par.record = 1
_ck.par.active = 1
_tmr.par.start.pulse()
print("recording", MINUTES, "min to", _rec.par.file.eval())
