"""Record the mapper output, what the projector sees, to an mp4 for ten minutes.

    exec(open('~/dev/studio_visuals/td/record.py').read())

Writes TD_Mapping/Recordings/studio_<date>.mp4 and stops on its own. To stop early:
    op('/project1/rec').par.record = 0
Running it again while a recording is on restarts the ten minutes into a new file.
"""
import datetime
import os

MINUTES = 10
_proj = op("/project1")
_rec = _proj.op("rec") or _proj.create(moviefileoutTOP, "rec")
_tmr = _proj.op("rec_timer") or _proj.create(timerCHOP, "rec_timer")
_rec.par.record = 0
_rec.inputConnectors[0].connect(_proj.op("kantanMapper1/out1").outputConnectors[0])
_out = os.path.join(project.folder, "Recordings")
os.makedirs(_out, exist_ok=True)
_rec.par.file = os.path.join(_out, "studio_" + datetime.datetime.now().strftime("%Y%m%d_%H%M") + ".mp4")
_rec.par.type = "mp4"
_rec.par.videocodec = "h264"
_tmr.par.lengthunits = "seconds"
_tmr.par.length = MINUTES * 60
_tmr.par.callbacks = "rec_timer_cb"
_cb = _proj.op("rec_timer_cb") or _proj.create(textDAT, "rec_timer_cb")
_cb.text = "def onDone(timerOp, segment, interrupt):\n    op('/project1/rec').par.record = 0\n    print('recording done')\n    return\n"
_rec.par.record = 1
_tmr.par.start.pulse()
print("recording", MINUTES, "min to", _rec.par.file.eval())
