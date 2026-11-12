"""Show the mapper's output in a window on this screen, for working without the projector.

Run inside TouchDesigner, from the Textport:
    exec(open(project.folder + '/../td/open_output.py').read())

The mapper's own output window (kantanMapper1/project/window1, the Toggle Output button) goes
borderless to display 1, the projector. This one opens the project's spare Window COMP on the
same TOP at half size with borders, on whatever screen the mouse is on.
"""
out = op('/project1/kantanMapper1/out1')
w = op('/project1/window')
w.par.winclose.pulse()
w.par.winop = out.path
w.par.title = 'mapper output'
w.par.size = 'custom'
w.par.winw = 960
w.par.winh = 540
w.par.borders = True
w.par.justifyh = 'center'
w.par.justifyv = 'center'  # the save had 'top', which put the title bar off screen
w.par.winopen.pulse()
print('opened', w.par.title.eval(), 'on', out.path)
