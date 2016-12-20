#!/bin/bash
for i in $( ls filters ); do
	( cd filters/$i && gcc -Wall -fPIC -c $i"_filter.c"  \
	  && gcc -shared -Wl,-soname,"lib_"$i".so.1" -o $i".so" $i"_filter.o" \
	  && if [ -f $i".so" ];
		then
			cp -f $i".so" /usr/lib64/tcmu-filters
		else
   			echo "File $i".so" does not exist."
		fi
        )
done
